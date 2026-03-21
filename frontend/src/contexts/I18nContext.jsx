import { createContext, useContext, useState, useCallback } from 'react';
import zh from '../locales/zh.json';
import en from '../locales/en.json';

const locales = { zh, en };
const I18nContext = createContext();

export function I18nProvider({ children }) {
  const [locale, setLocale] = useState(() => {
    return localStorage.getItem('locale') || 'zh';
  });

  const t = useCallback((key) => {
    return locales[locale]?.[key] || locales.zh[key] || key;
  }, [locale]);

  const switchLocale = useCallback((newLocale) => {
    setLocale(newLocale);
    localStorage.setItem('locale', newLocale);
  }, []);

  return (
    <I18nContext.Provider value={{ locale, t, switchLocale }}>
      {children}
    </I18nContext.Provider>
  );
}

export const useI18n = () => useContext(I18nContext);
