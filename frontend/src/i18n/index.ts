import i18n from "i18next"
import LanguageDetector from "i18next-browser-languagedetector"
import { initReactI18next } from "react-i18next"

import enAdmin from "./locales/en/admin.json"
import enAuth from "./locales/en/auth.json"
import enCommon from "./locales/en/common.json"
import enDashboard from "./locales/en/dashboard.json"
import enIngredients from "./locales/en/ingredients.json"
import enNavigation from "./locales/en/navigation.json"
import enRecipes from "./locales/en/recipes.json"
import enSettings from "./locales/en/settings.json"
import enShopping from "./locales/en/shopping.json"
import frAdmin from "./locales/fr/admin.json"
import frAuth from "./locales/fr/auth.json"
import frCommon from "./locales/fr/common.json"
import frDashboard from "./locales/fr/dashboard.json"
import frIngredients from "./locales/fr/ingredients.json"
import frNavigation from "./locales/fr/navigation.json"
import frRecipes from "./locales/fr/recipes.json"
import frSettings from "./locales/fr/settings.json"
import frShopping from "./locales/fr/shopping.json"

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: {
        common: enCommon,
        navigation: enNavigation,
        auth: enAuth,
        recipes: enRecipes,
        ingredients: enIngredients,
        shopping: enShopping,
        settings: enSettings,
        admin: enAdmin,
        dashboard: enDashboard,
      },
      fr: {
        common: frCommon,
        navigation: frNavigation,
        auth: frAuth,
        recipes: frRecipes,
        ingredients: frIngredients,
        shopping: frShopping,
        settings: frSettings,
        admin: frAdmin,
        dashboard: frDashboard,
      },
    },
    defaultNS: "common",
    fallbackLng: "en",
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ["localStorage", "navigator"],
      lookupLocalStorage: "i18n-language",
      caches: ["localStorage"],
    },
  })

export default i18n
