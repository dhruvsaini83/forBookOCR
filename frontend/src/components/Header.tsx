import React, { useState, useEffect } from 'react';
import { 
  UploadCloud, BookOpen, BarChart3, Sparkles, Globe2, 
  ShieldCheck, Menu, X 
} from 'lucide-react';
import type { Language } from '../i18n/translations';
import { translations } from '../i18n/translations';

interface HeaderProps {
  lang: Language;
  onToggleLang: () => void;
  onChangeLang?: (lang: Language) => void;
  onOpenUpload: () => void;
  onOpenHistory: () => void;
  onOpenBenchmark: () => void;
  onOpenSamples: () => void;
  activeDocTitle?: string;
}

export const Header: React.FC<HeaderProps> = ({
  lang,
  onToggleLang,
  onChangeLang,
  onOpenUpload,
  onOpenHistory,
  onOpenBenchmark,
  onOpenSamples,
  activeDocTitle,
}) => {
  const t = translations[lang];
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Close mobile menu on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setMobileMenuOpen(false);
      }
    };
    if (mobileMenuOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [mobileMenuOpen]);

  const handleSelectLanguage = (targetLang: Language) => {
    if (onChangeLang) {
      onChangeLang(targetLang);
    } else if (lang !== targetLang) {
      onToggleLang();
    }
  };

  return (
    <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-md border-b border-stone-200/90 shadow-2xs">
      <div className="max-w-7xl w-full mx-auto px-3 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 sm:h-20 gap-2">
          {/* Brand & Title */}
          <div className="flex items-center gap-2 sm:gap-3.5 min-w-0 shrink">
            <div className="w-9 h-9 sm:w-11 sm:h-11 rounded-xl sm:rounded-2xl bg-gradient-to-tr from-vedic-700 via-vedic-600 to-saffron-500 p-0.5 shadow-2xs flex items-center justify-center shrink-0">
              <div className="w-full h-full bg-vedic-950 rounded-[10px] sm:rounded-[13px] flex items-center justify-center text-white font-bold text-lg sm:text-2xl font-traditional">
                वा
              </div>
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 sm:gap-2">
                <h1 className="text-lg sm:text-2xl font-bold font-devanagari text-vedic-950 tracking-tight truncate">
                  {t.appTitle}
                </h1>
                <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-300 shrink-0">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                  <span>{lang === 'hi' ? '५-चरणीय सत्यापन' : '5-Stage Verified'}</span>
                </span>
              </div>
              <p className="text-[11px] text-stone-500 hidden md:block font-devanagari truncate">
                {t.appSubtitle}
              </p>
            </div>
          </div>

          {/* Center: Active Document Badge (Desktop) */}
          {activeDocTitle && (
            <div className="hidden xl:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-vedic-50/80 border border-vedic-200 max-w-xs truncate shadow-2xs">
              <BookOpen className="w-4 h-4 text-vedic-700 shrink-0" />
              <span className="text-xs font-medium text-vedic-950 truncate font-devanagari">
                {activeDocTitle}
              </span>
            </div>
          )}

          {/* Desktop Navigation Action Buttons (>= 768px) */}
          <div className="hidden md:flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={onOpenUpload}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-vedic-700 hover:bg-vedic-800 active:bg-vedic-900 text-white font-medium text-xs sm:text-sm shadow-xs transition-colors font-devanagari"
              aria-label={t.navUpload}
            >
              <UploadCloud className="w-4 h-4" />
              <span>{t.navUpload}</span>
            </button>

            <button
              type="button"
              onClick={onOpenHistory}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-stone-200 hover:bg-stone-50 text-stone-700 font-medium text-xs sm:text-sm transition-colors font-devanagari"
              title={t.navHistory}
              aria-label={t.navHistory}
            >
              <BookOpen className="w-4 h-4 text-vedic-700" />
              <span>{t.navHistory}</span>
            </button>

            <button
              type="button"
              onClick={onOpenSamples}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-stone-200 hover:bg-stone-50 text-stone-700 font-medium text-xs sm:text-sm transition-colors font-devanagari"
              title={t.navSamples}
              aria-label={t.navSamples}
            >
              <Sparkles className="w-4 h-4 text-amber-600" />
              <span>{t.navSamples}</span>
            </button>

            <button
              type="button"
              onClick={onOpenBenchmark}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-stone-200 hover:bg-stone-50 text-stone-700 font-medium text-xs sm:text-sm transition-colors font-devanagari"
              title={t.navBenchmark}
              aria-label={t.navBenchmark}
            >
              <BarChart3 className="w-4 h-4 text-indigo-600" />
              <span>{t.navBenchmark}</span>
            </button>

            {/* Desktop Hindi / English Segmented Switch */}
            <div 
              role="group" 
              aria-label="Language selection" 
              className="flex items-center bg-stone-100 p-0.5 rounded-xl border border-stone-200/90 shadow-2xs ml-1"
            >
              <button
                type="button"
                onClick={() => handleSelectLanguage('hi')}
                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-devanagari transition-all duration-150 ${
                  lang === 'hi'
                    ? 'bg-vedic-700 text-white font-bold shadow-xs'
                    : 'text-stone-600 hover:text-stone-900 font-medium'
                }`}
                title="हिंदी में वेबसाइट देखें"
                aria-pressed={lang === 'hi'}
              >
                <Globe2 className="w-3.5 h-3.5" />
                <span>हिंदी</span>
              </button>
              <button
                type="button"
                onClick={() => handleSelectLanguage('en')}
                className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-sans transition-all duration-150 ${
                  lang === 'en'
                    ? 'bg-vedic-700 text-white font-bold shadow-xs'
                    : 'text-stone-600 hover:text-stone-900 font-medium'
                }`}
                title="View website in English"
                aria-pressed={lang === 'en'}
              >
                <span>English</span>
              </button>
            </div>
          </div>

          {/* Mobile Right Controls (< 768px): Compact Language Toggle + Upload Icon + Mobile Menu Toggle */}
          <div className="flex md:hidden items-center gap-1.5 shrink-0">
            {/* Compact Language Toggle */}
            <div 
              role="group" 
              aria-label="Language selection" 
              className="flex items-center bg-stone-100 p-0.5 rounded-lg border border-stone-200 text-xs"
            >
              <button
                type="button"
                onClick={() => handleSelectLanguage('hi')}
                className={`px-2 py-1 rounded-md text-[11px] font-devanagari ${
                  lang === 'hi'
                    ? 'bg-vedic-700 text-white font-bold shadow-2xs'
                    : 'text-stone-600 hover:text-stone-900'
                }`}
                aria-label="Switch to Hindi"
                aria-pressed={lang === 'hi'}
              >
                हिं
              </button>
              <button
                type="button"
                onClick={() => handleSelectLanguage('en')}
                className={`px-2 py-1 rounded-md text-[11px] font-sans ${
                  lang === 'en'
                    ? 'bg-vedic-700 text-white font-bold shadow-2xs'
                    : 'text-stone-600 hover:text-stone-900'
                }`}
                aria-label="Switch to English"
                aria-pressed={lang === 'en'}
              >
                En
              </button>
            </div>

            {/* Quick Upload Icon Button */}
            <button
              type="button"
              onClick={onOpenUpload}
              className="p-2 rounded-xl bg-vedic-700 hover:bg-vedic-800 text-white shadow-2xs transition-colors"
              title={t.navUpload}
              aria-label={t.navUpload}
            >
              <UploadCloud className="w-4 h-4" />
            </button>

            {/* Hamburger Menu Toggle */}
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-xl border border-stone-200 bg-white hover:bg-stone-50 text-stone-700 transition-colors"
              title={mobileMenuOpen ? t.close : t.menu}
              aria-label={mobileMenuOpen ? t.close : t.menu}
              aria-expanded={mobileMenuOpen}
            >
              {mobileMenuOpen ? <X className="w-5 h-5 text-stone-800" /> : <Menu className="w-5 h-5 text-stone-800" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Drawer / Dropdown Menu */}
      {mobileMenuOpen && (
        <div 
          className="md:hidden border-t border-stone-200 bg-white/98 backdrop-blur-md px-4 py-3 shadow-lg animate-in fade-in slide-in-from-top-2 duration-150"
          role="dialog"
          aria-label="Mobile Navigation"
        >
          {activeDocTitle && (
            <div className="mb-3 p-2.5 rounded-xl bg-vedic-50 border border-vedic-200 text-xs font-devanagari text-vedic-950 flex items-center gap-2">
              <BookOpen className="w-4 h-4 text-vedic-700 shrink-0" />
              <span className="truncate">{activeDocTitle}</span>
            </div>
          )}

          <div className="grid grid-cols-1 gap-2">
            <button
              type="button"
              onClick={() => {
                onOpenUpload();
                setMobileMenuOpen(false);
              }}
              className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl bg-vedic-700 text-white font-semibold text-xs font-devanagari text-left shadow-2xs"
            >
              <UploadCloud className="w-4 h-4" />
              <span>{t.navUpload}</span>
            </button>

            <button
              type="button"
              onClick={() => {
                onOpenHistory();
                setMobileMenuOpen(false);
              }}
              className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl border border-stone-200 hover:bg-stone-50 text-stone-800 font-medium text-xs font-devanagari text-left"
            >
              <BookOpen className="w-4 h-4 text-vedic-700" />
              <span>{t.navHistory}</span>
            </button>

            <button
              type="button"
              onClick={() => {
                onOpenSamples();
                setMobileMenuOpen(false);
              }}
              className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl border border-stone-200 hover:bg-stone-50 text-stone-800 font-medium text-xs font-devanagari text-left"
            >
              <Sparkles className="w-4 h-4 text-amber-600" />
              <span>{t.navSamples}</span>
            </button>

            <button
              type="button"
              onClick={() => {
                onOpenBenchmark();
                setMobileMenuOpen(false);
              }}
              className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl border border-stone-200 hover:bg-stone-50 text-stone-800 font-medium text-xs font-devanagari text-left"
            >
              <BarChart3 className="w-4 h-4 text-indigo-600" />
              <span>{t.navBenchmark}</span>
            </button>
          </div>

          <div className="mt-3 pt-2.5 border-t border-stone-100 flex items-center justify-between text-[11px] text-stone-500 font-devanagari">
            <span>वाणीसंशोधक v2.1.0</span>
            <span className="flex items-center gap-1 text-emerald-700 font-semibold">
              <ShieldCheck className="w-3.5 h-3.5" />
              {lang === 'hi' ? '५-चरणीय सत्यापन' : '5-Stage Verified'}
            </span>
          </div>
        </div>
      )}
    </header>
  );
};
