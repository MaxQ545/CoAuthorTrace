import { createContext, useContext, useState, useCallback, useMemo } from 'react';
import zh from '../locales/zh.json';
import en from '../locales/en.json';

const locales = { zh, en };

const I18nContext = createContext();

export function I18nProvider({ children }) {
  const [locale, setLocale] = useState(() => {
    return localStorage.getItem('locale') || 'zh';
  });

  const changeLocale = useCallback((newLocale) => {
    setLocale(newLocale);
    localStorage.setItem('locale', newLocale);
  }, []);

  const t = useCallback((key, params = {}) => {
    let text = locales[locale]?.[key] || locales.zh[key] || key;
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(`{${k}}`, v);
    });
    return text;
  }, [locale]);

  const value = useMemo(() => ({
    locale,
    setLocale: changeLocale,
    t,
  }), [locale, changeLocale, t]);

  return (
    <I18nContext.Provider value={value}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used within an I18nProvider');
  }
  return context;
}

export default I18nContext;
