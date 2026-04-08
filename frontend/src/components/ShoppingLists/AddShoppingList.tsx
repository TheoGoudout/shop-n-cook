import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { ShoppingListsService } from "@/client"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

function isoWeekNumber(d: Date): number {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  const day = date.getUTCDay() || 7
  date.setUTCDate(date.getUTCDate() + 4 - day)
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1))
  return Math.ceil(((date.getTime() - yearStart.getTime()) / 86400000 + 1) / 7)
}

function toDateInput(d: Date): string {
  return d.toISOString().split("T")[0]
}

function getDefaultListDefaults() {
  const now = new Date()
  const day = now.getDay()
  const diff = day === 0 ? -6 : 1 - day // shift to Monday
  const monday = new Date(now)
  monday.setDate(now.getDate() + diff)
  const sunday = new Date(monday)
  sunday.setDate(monday.getDate() + 6)

  const weekNum = isoWeekNumber(now)
  const fmt = (d: Date) =>
    d.toLocaleDateString(undefined, { day: "numeric", month: "short" })

  return {
    name: `Week #${weekNum} · ${fmt(monday)} – ${fmt(sunday)}`,
    start_date: toDateInput(monday),
    end_date: toDateInput(sunday),
  }
}

const formSchema = z.object({
  name: z.string().min(1, { message: "Name is required" }),
  start_date: z.string().optional(),
  end_date: z.string().optional(),
})

type FormData = z.infer<typeof formSchema>

const AddShoppingList = () => {
  const [isOpen, setIsOpen] = useState(false)
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: getDefaultListDefaults(),
  })

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      ShoppingListsService.createShoppingList({
        requestBody: {
          name: data.name,
          start_date: data.start_date || null,
          end_date: data.end_date || null,
        },
      }),
    onSuccess: () => {
      showSuccessToast("Shopping list created")
      form.reset(getDefaultListDefaults())
      setIsOpen(false)
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () =>
      queryClient.invalidateQueries({ queryKey: ["shopping-lists"] }),
  })

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        setIsOpen(open)
        if (open) form.reset(getDefaultListDefaults())
      }}
    >
      <DialogTrigger asChild>
        <Button className="my-4">
          <Plus className="mr-2" />
          New List
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New Shopping List</DialogTitle>
          <DialogDescription>
            Give your shopping list a name and optional date range.
          </DialogDescription>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit((d) => mutation.mutate(d))}>
            <div className="grid gap-4 py-4">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>
                      Name <span className="text-destructive">*</span>
                    </FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. Weekly groceries" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <div className="grid grid-cols-2 gap-3">
                <FormField
                  control={form.control}
                  name="start_date"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Start date</FormLabel>
                      <FormControl>
                        <Input type="date" {...field} />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="end_date"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>End date</FormLabel>
                      <FormControl>
                        <Input type="date" {...field} />
                      </FormControl>
                    </FormItem>
                  )}
                />
              </div>
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button variant="outline" disabled={mutation.isPending}>
                  Cancel
                </Button>
              </DialogClose>
              <LoadingButton type="submit" loading={mutation.isPending}>
                Create
              </LoadingButton>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

export default AddShoppingList
