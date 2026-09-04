import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import enDictionary from "../locales/en.json";
import trDictionary from "../locales/tr.json";
import deDictionary from "../locales/de.json";
import { apiFetch, apiUrl } from "../lib/backend";

export type Locale = "en" | "tr" | "de";

export const SUPPORTED_LOCALES: { id: Locale; label: string; flag: string }[] = [
  { id: "en", label: "English", flag: "US" },
  { id: "tr", label: "Türkçe", flag: "TR" },
  { id: "de", label: "Deutsch", flag: "DE" },
];

const DICTIONARIES: Record<Locale, any> = {
  en: enDictionary,
  tr: trDictionary,
  de: deDictionary,
};

interface I18nContextType {
  locale: Locale;
  setLocale: (loc: Locale) => void;
  t: (path: string, params?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nContextType | undefined>(undefined);

function getNestedValue(obj: any, path: string): string | undefined {
  if (!obj || typeof obj !== "object") return undefined;
  const parts = path.split(".");
  let curr = obj;
  for (const part of parts) {
    if (curr && typeof curr === "object" && part in curr) {
      curr = curr[part];
    } else {
      return undefined;
    }
  }
  return typeof curr === "string" ? curr : undefined;
}

export const I18nProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [locale, setLocaleState] = useState<Locale>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("kuantra_locale") as Locale;
      if (saved === "en" || saved === "tr" || saved === "de") return saved;
    }
    return "en";
  });

  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    if (typeof window !== "undefined") {
      localStorage.setItem("kuantra_locale", newLocale);
    }

    // Sync with backend asynchronously
    apiFetch(apiUrl("/api/v1/settings"), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active_locale: newLocale }),
    }).catch(() => {});
  }, []);

  useEffect(() => {
    apiFetch(apiUrl("/api/v1/settings"))
      .then((res) => res.json())
      .then((data) => {
        if (data && (data.active_locale === "en" || data.active_locale === "tr" || data.active_locale === "de")) {
          if (data.active_locale !== locale) {
            setLocaleState(data.active_locale);
            if (typeof window !== "undefined") {
              localStorage.setItem("kuantra_locale", data.active_locale);
            }
          }
        }
      })
      .catch(() => {});
  }, []);

  const t = useCallback(
    (path: string, params?: Record<string, string | number>): string => {
      const activeDict = DICTIONARIES[locale] || DICTIONARIES.en;
      let rawString = getNestedValue(activeDict, path);

      // Fallback to English dictionary if not found in active locale
      if (!rawString && locale !== "en") {
        rawString = getNestedValue(DICTIONARIES.en, path);
      }

      // Ultimate fallback is the path key
      if (!rawString) {
        return path;
      }

      // Handle dynamic string interpolation {key} or {{key}}
      if (params) {
        return Object.entries(params).reduce((str, [k, v]) => {
          return str.replace(new RegExp(`(?:\\{\\{|\\{)${k}(?:\\}\\}|\\})`, "g"), String(v));
        }, rawString);
      }

      return rawString;
    },
    [locale]
  );

  const value = {
    locale,
    setLocale,
    t,
  };

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
};

export const useTranslation = (): I18nContextType => {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useTranslation must be used within an I18nProvider");
  }
  return context;
};