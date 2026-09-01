import i18n from "i18next"
import { Camera, ImagePlus, Loader2, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { ApiError, RecipesService } from "@/client"
import { Button } from "@/components/ui/button"
import useCustomToast from "@/hooks/useCustomToast"
import { downscaleImage } from "@/lib/imageDownscale"

import { parsedRecipeToFormValues } from "./parsedRecipeToFormValues"
import type { RecipeFormValues } from "./recipeFormSchema"

/** Keep in step with RECIPE_PHOTO_MAX_COUNT on the backend. */
export const MAX_PHOTOS = 3

interface Props {
  onImported: (values: RecipeFormValues) => void
}

interface SelectedPhoto {
  file: File
  previewUrl: string
}

export function RecipePhotoImportPanel({ onImported }: Props) {
  const { t } = useTranslation("recipes")
  const { t: tCommon } = useTranslation("common")
  const { showSuccessToast, showErrorToast } = useCustomToast()
  const [photos, setPhotos] = useState<SelectedPhoto[]>([])
  const [isImporting, setIsImporting] = useState(false)
  const cameraInputRef = useRef<HTMLInputElement>(null)
  const galleryInputRef = useRef<HTMLInputElement>(null)

  // Object URLs are only reclaimed on explicit revoke, so release them when the
  // panel goes away (the Add Recipe dialog unmounts on close).
  useEffect(() => {
    return () => {
      for (const photo of photos) URL.revokeObjectURL(photo.previewUrl)
    }
  }, [photos])

  const addFiles = (fileList: FileList | null) => {
    if (!fileList?.length) return
    const incoming = Array.from(fileList)
    const room = MAX_PHOTOS - photos.length
    if (incoming.length > room) {
      showErrorToast(t("add.photo_too_many", { max: MAX_PHOTOS }))
    }
    const accepted = incoming.slice(0, Math.max(0, room))
    if (!accepted.length) return
    setPhotos((current) => [
      ...current,
      ...accepted.map((file) => ({
        file,
        previewUrl: URL.createObjectURL(file),
      })),
    ])
  }

  const removePhoto = (index: number) => {
    setPhotos((current) => {
      const removed = current[index]
      if (removed) URL.revokeObjectURL(removed.previewUrl)
      return current.filter((_, i) => i !== index)
    })
  }

  const clearPhotos = () => {
    setPhotos((current) => {
      for (const photo of current) URL.revokeObjectURL(photo.previewUrl)
      return []
    })
  }

  const handleImport = async () => {
    if (!photos.length) return
    setIsImporting(true)
    try {
      const downscaled = await Promise.all(
        photos.map((photo) => downscaleImage(photo.file)),
      )
      const parsed = await RecipesService.importRecipePhotos({
        formData: { photos: downscaled, language: i18n.language },
      })
      onImported(parsedRecipeToFormValues(parsed, "photo"))
      clearPhotos()
      showSuccessToast(t("add.photo_import_success"))
    } catch (error) {
      if (error instanceof ApiError && error.status === 429) {
        showErrorToast(t("add.photo_rate_limited"))
      } else if (
        error instanceof ApiError &&
        (error.body as { detail?: string } | undefined)?.detail ===
          "no_recipe_found"
      ) {
        showErrorToast(t("add.photo_import_no_recipe"))
      } else {
        showErrorToast(t("add.photo_import_error"))
      }
    } finally {
      setIsImporting(false)
    }
  }

  const isFull = photos.length >= MAX_PHOTOS

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        {t("add.photo_import_hint", { max: MAX_PHOTOS })}
      </p>

      {/* Kept in the DOM (not `hidden`) so file selection is scriptable. */}
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="sr-only"
        aria-label={t("add.photo_take_photo")}
        onChange={(e) => {
          addFiles(e.target.files)
          e.target.value = ""
        }}
      />
      <input
        ref={galleryInputRef}
        type="file"
        accept="image/*"
        multiple
        className="sr-only"
        aria-label={t("add.photo_choose_images")}
        onChange={(e) => {
          addFiles(e.target.files)
          e.target.value = ""
        }}
      />

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={isFull || isImporting}
          onClick={() => cameraInputRef.current?.click()}
        >
          <Camera className="h-4 w-4" />
          <span className="ml-1.5">{t("add.photo_take_photo")}</span>
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={isFull || isImporting}
          onClick={() => galleryInputRef.current?.click()}
        >
          <ImagePlus className="h-4 w-4" />
          <span className="ml-1.5">{t("add.photo_choose_images")}</span>
        </Button>
      </div>

      {photos.length > 0 && (
        <>
          <ul className="flex flex-wrap gap-2">
            {photos.map((photo, index) => (
              <li key={photo.previewUrl} className="relative">
                <img
                  src={photo.previewUrl}
                  alt=""
                  className="h-20 w-20 rounded-md border object-cover"
                />
                <button
                  type="button"
                  aria-label={t("add.photo_remove")}
                  onClick={() => removePhoto(index)}
                  disabled={isImporting}
                  className="absolute -right-1.5 -top-1.5 rounded-full bg-background border p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-50"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </li>
            ))}
          </ul>

          <div className="flex items-center justify-between gap-2">
            <span className="text-sm text-muted-foreground">
              {t("add.photo_selected", { count: photos.length })}
            </span>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={handleImport}
              disabled={isImporting}
            >
              {isImporting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <ImagePlus className="h-4 w-4" />
              )}
              <span className="ml-1.5">{tCommon("import")}</span>
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
