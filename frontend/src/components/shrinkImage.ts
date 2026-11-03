/** Downscales a phone photo before upload: a 12 MP camera shot becomes ~200 KB, which
 * matters on mobile data. Text stays readable for OCR at 1600 px wide. */
export async function shrinkImage(file: File, maxSide = 1600, quality = 0.88): Promise<File> {
  if (!file.type.startsWith('image/') || file.size < 400_000) return file
  try {
    const bitmap = await createImageBitmap(file)
    const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(bitmap.width * scale)
    canvas.height = Math.round(bitmap.height * scale)
    canvas.getContext('2d')?.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    bitmap.close()
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality))
    return blob && blob.size < file.size ? new File([blob], 'document.jpg', { type: 'image/jpeg' }) : file
  } catch {
    return file // older browsers: send the original
  }
}
