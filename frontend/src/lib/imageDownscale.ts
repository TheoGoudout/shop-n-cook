/** Longest edge, in pixels, that vision models actually consume. */
export const MAX_PHOTO_EDGE = 1568
/** Files already smaller than this are sent untouched. */
const SKIP_BELOW_BYTES = 1024 * 1024
const JPEG_QUALITY = 0.82

/**
 * Shrink a photo before uploading it.
 *
 * A phone camera produces multi-megabyte images at resolutions far beyond what
 * the vision model reads, so they are resampled to `maxEdge` and re-encoded as
 * JPEG — typically a ~6 MB photo down to a few hundred KB.
 *
 * Never throws: any failure (unsupported codec, no canvas, blocked bitmap)
 * returns the original file, which the server validates anyway.
 */
export async function downscaleImage(
  file: File,
  maxEdge: number = MAX_PHOTO_EDGE,
  quality: number = JPEG_QUALITY,
): Promise<File> {
  let bitmap: ImageBitmap | undefined
  try {
    bitmap = await createImageBitmap(file)
    const longestEdge = Math.max(bitmap.width, bitmap.height)
    if (longestEdge <= maxEdge && file.size <= SKIP_BELOW_BYTES) {
      return file
    }

    const scale = Math.min(1, maxEdge / longestEdge)
    const width = Math.max(1, Math.round(bitmap.width * scale))
    const height = Math.max(1, Math.round(bitmap.height * scale))

    const canvas = document.createElement("canvas")
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext("2d")
    if (!context) return file
    context.drawImage(bitmap, 0, 0, width, height)

    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, "image/jpeg", quality)
    })
    if (!blob) return file

    return new File([blob], `${file.name.replace(/\.[^.]+$/, "")}.jpg`, {
      type: "image/jpeg",
      lastModified: Date.now(),
    })
  } catch {
    return file
  } finally {
    bitmap?.close()
  }
}
