const translations = {
  en: {
    loading: "Loading…",
    logout: "Logout",
    signIn: "Sign in",
    signingIn: "Signing in…",
    email: "Email",
    password: "Password",
    serverUrl: "Server URL",
    advancedCollapsed: "Advanced ▸",
    advancedExpanded: "Advanced ▾",
    errorFillAllFields: "Please fill in all fields.",
    errorLoginFailed: "Login failed. Check your credentials and server URL.",
    consentText:
      "The recipe is sourced from a third-party website. By importing, you confirm you have the right to store and reformat this content for personal use and will respect the original author's intellectual property rights. This app does not claim any rights over imported content and always links back to the original source.",
    importRecipe: "Import Recipe",
    analyzingPage: "Analyzing the page with AI…",
    importing: "Importing…",
    openInApp: "Open in app ↗",
    importAnother: "Import another",
    tryAgain: "Try again",
    errorNotARecipePage:
      "Cannot import from this page. Navigate to a recipe URL first.",
    errorUnexpected: "An unexpected error occurred.",
    errorSessionExpired: "Session expired. Please sign in again.",
  },
  fr: {
    loading: "Chargement…",
    logout: "Déconnexion",
    signIn: "Se connecter",
    signingIn: "Connexion…",
    email: "E-mail",
    password: "Mot de passe",
    serverUrl: "URL du serveur",
    advancedCollapsed: "Avancé ▸",
    advancedExpanded: "Avancé ▾",
    errorFillAllFields: "Veuillez remplir tous les champs.",
    errorLoginFailed:
      "Échec de la connexion. Vérifiez vos identifiants et l'URL du serveur.",
    consentText:
      "La recette provient d'un site tiers. En important, vous confirmez avoir le droit de stocker et reformater ce contenu à des fins personnelles, et vous vous engagez à respecter les droits de propriété intellectuelle de l'auteur original. Cette application ne revendique aucun droit sur le contenu importé et renvoie toujours vers la source originale.",
    importRecipe: "Importer la recette",
    analyzingPage: "Analyse de la page avec l'IA…",
    importing: "Importation…",
    openInApp: "Ouvrir dans l'app ↗",
    importAnother: "Importer une autre",
    tryAgain: "Réessayer",
    errorNotARecipePage:
      "Impossible d'importer depuis cette page. Accédez d'abord à l'URL d'une recette.",
    errorUnexpected: "Une erreur inattendue s'est produite.",
    errorSessionExpired: "Session expirée. Veuillez vous reconnecter.",
  },
} as const

type Lang = keyof typeof translations
type TranslationKey = keyof typeof translations.en

let lang: Lang = detectLang()

function detectLang(): Lang {
  const code = navigator.language?.slice(0, 2).toLowerCase()
  return code === "fr" ? "fr" : "en"
}

export function setLang(code: string): void {
  lang = code.slice(0, 2).toLowerCase() === "fr" ? "fr" : "en"
}

export function getLang(): Lang {
  return lang
}

export function t(key: TranslationKey): string {
  return translations[lang][key]
}
