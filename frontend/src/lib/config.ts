export const APP_NAME = (import.meta.env.VITE_PROJECT_NAME as string)
  .replace(/\\'/g, "'")
  .replace(/\\"/g, '"')
