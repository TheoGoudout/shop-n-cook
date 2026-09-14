import { useQuery } from "@tanstack/react-query"
import { Mail, Trash2, UserMinus } from "lucide-react"
import { type ReactNode, useState } from "react"
import { useTranslation } from "react-i18next"

import { type ApiError, HouseholdsService } from "@/client"
import { ConfirmDialog } from "@/components/Common/ConfirmDialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { LoadingButton } from "@/components/ui/loading-button"
import { useCrudMutation } from "@/hooks/useCrudMutation"

const HOUSEHOLD_KEY = ["household"] as const

/** ConfirmDialog is controlled; every use here is the same button-and-confirm. */
function ConfirmButton({
  title,
  description,
  isPending,
  onConfirm,
  children,
}: {
  title: string
  description?: string
  isPending: boolean
  onConfirm: () => void
  children: ReactNode
}) {
  const [open, setOpen] = useState(false)
  return (
    <ConfirmDialog
      open={open}
      onOpenChange={setOpen}
      title={title}
      description={description}
      variant="destructive"
      isPending={isPending}
      onConfirm={() => {
        onConfirm()
        setOpen(false)
      }}
      trigger={
        <span role="none" onClick={() => setOpen(true)}>
          {children}
        </span>
      }
    />
  )
}

/**
 * Create, join and manage the household a user shares lists and plans with.
 *
 * "Not in a household" is a 404 from the API rather than an error state, so it
 * is rendered as the create form instead of a failure.
 */
export function HouseholdSharing() {
  const { t } = useTranslation("settings")
  const { t: tCommon } = useTranslation("common")
  const [name, setName] = useState("")
  const [inviteEmail, setInviteEmail] = useState("")

  const { data: household, isLoading } = useQuery({
    queryKey: HOUSEHOLD_KEY,
    queryFn: () => HouseholdsService.readMyHousehold(),
    // A user with no household is the normal first-run state, not a failure.
    retry: (_count, error) => (error as ApiError)?.status !== 404,
  })

  const create = useCrudMutation({
    mutationFn: () =>
      HouseholdsService.createHousehold({ requestBody: { name } }),
    successMessage: t("household_sharing.created"),
    invalidateKeys: [HOUSEHOLD_KEY],
    onSuccess: () => setName(""),
  })

  const invite = useCrudMutation({
    mutationFn: () =>
      HouseholdsService.inviteMember({ requestBody: { email: inviteEmail } }),
    successMessage: t("household_sharing.invited"),
    invalidateKeys: [HOUSEHOLD_KEY],
    onSuccess: () => setInviteEmail(""),
  })

  const revoke = useCrudMutation({
    mutationFn: (inviteId: string) =>
      HouseholdsService.revokeInvite({ inviteId }),
    successMessage: t("household_sharing.revoked"),
    invalidateKeys: [HOUSEHOLD_KEY],
  })

  // Sharing changes what these queries return, so they are invalidated too.
  const sharedKeys = [
    HOUSEHOLD_KEY,
    ["shopping-lists"],
    ["meal-plans"],
  ] as const

  const removeMember = useCrudMutation({
    mutationFn: (memberId: string) =>
      HouseholdsService.removeMember({ memberId }),
    successMessage: t("household_sharing.removed"),
    invalidateKeys: [...sharedKeys],
  })

  const leave = useCrudMutation({
    mutationFn: () => HouseholdsService.leaveMyHousehold(),
    successMessage: t("household_sharing.left"),
    invalidateKeys: [...sharedKeys],
  })

  const disband = useCrudMutation({
    mutationFn: () => HouseholdsService.deleteMyHousehold(),
    successMessage: t("household_sharing.disbanded"),
    invalidateKeys: [...sharedKeys],
  })

  if (isLoading) {
    return (
      <p className="text-sm text-muted-foreground">
        {tCommon("loading", { defaultValue: "Loading…" })}
      </p>
    )
  }

  if (!household) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("household_sharing.title")}</CardTitle>
          <CardDescription>
            {t("household_sharing.none_description")}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="household-name">
              {t("household_sharing.name_label")}
            </Label>
            <Input
              id="household-name"
              value={name}
              placeholder={t("household_sharing.name_placeholder")}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <LoadingButton
            loading={create.isPending}
            disabled={name.trim() === ""}
            onClick={() => create.mutate()}
          >
            {t("household_sharing.create")}
          </LoadingButton>
        </CardContent>
      </Card>
    )
  }

  const isOwner = household.members?.some(
    (m) => m.user_id === household.owner_id && m.role === "owner",
  )
  const seats = household.seats_remaining ?? 0

  return (
    <Card>
      <CardHeader>
        <CardTitle>{household.name}</CardTitle>
        <CardDescription>{t("household_sharing.description")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <p className="text-sm font-medium">
            {t("household_sharing.members")}
          </p>
          {(household.members ?? []).map((member) => (
            <div key={member.id} className="flex items-center gap-2 text-sm">
              <span className="flex-1 truncate">
                {member.full_name || member.email}
              </span>
              <Badge variant="secondary" className="text-xs">
                {t(`household_sharing.role_${member.role}`)}
              </Badge>
              {isOwner && member.role !== "owner" && (
                <ConfirmButton
                  title={t("household_sharing.remove")}
                  description={member.email}
                  isPending={removeMember.isPending}
                  onConfirm={() => removeMember.mutate(member.id)}
                >
                  <Button variant="ghost" size="icon" className="h-6 w-6">
                    <UserMinus className="h-3 w-3" />
                  </Button>
                </ConfirmButton>
              )}
            </div>
          ))}
        </div>

        {(household.invites ?? []).length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium">
              {t("household_sharing.invites")}
            </p>
            {(household.invites ?? []).map((pending) => (
              <div key={pending.id} className="flex items-center gap-2 text-sm">
                <Mail className="h-3 w-3 text-muted-foreground shrink-0" />
                <span className="flex-1 truncate text-muted-foreground">
                  {pending.email}
                </span>
                {isOwner && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6"
                    onClick={() => revoke.mutate(pending.id)}
                  >
                    {t("household_sharing.revoke")}
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}

        {isOwner && (
          <div className="space-y-2">
            <Label htmlFor="invite-email">
              {t("household_sharing.invite_label")}
            </Label>
            <div className="flex gap-2">
              <Input
                id="invite-email"
                type="email"
                value={inviteEmail}
                placeholder={t("household_sharing.invite_placeholder")}
                disabled={seats === 0}
                onChange={(e) => setInviteEmail(e.target.value)}
              />
              <LoadingButton
                loading={invite.isPending}
                disabled={inviteEmail.trim() === "" || seats === 0}
                onClick={() => invite.mutate()}
              >
                {t("household_sharing.invite")}
              </LoadingButton>
            </div>
            <p className="text-xs text-muted-foreground">
              {seats === 0
                ? t("household_sharing.full")
                : t("household_sharing.seats_remaining", { count: seats })}
            </p>
          </div>
        )}

        <div className="pt-2">
          {isOwner ? (
            <ConfirmButton
              title={t("household_sharing.disband")}
              description={t("household_sharing.disband_confirm")}
              isPending={disband.isPending}
              onConfirm={() => disband.mutate()}
            >
              <Button variant="outline">
                <Trash2 />
                {t("household_sharing.disband")}
              </Button>
            </ConfirmButton>
          ) : (
            <ConfirmButton
              title={t("household_sharing.leave")}
              description={t("household_sharing.leave_confirm")}
              isPending={leave.isPending}
              onConfirm={() => leave.mutate()}
            >
              <Button variant="outline">
                <UserMinus />
                {t("household_sharing.leave")}
              </Button>
            </ConfirmButton>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
