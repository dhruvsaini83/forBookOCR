import React from 'react';
import { UploadCloud, BookOpen, BarChart3, Sparkles, Globe2, ShieldCheck } from 'lucide-react';
import type { Language } from '../i18n/translations';
import { translations } from '../i18n/translations';

interface HeaderProps {
  lang: Language;
  onToggleLang: () => void;
  onOpenUpload: () => void;
  onOpenHistory: () => void;
  onOpenBenchmark: () => void;
  onOpenSamples: () => void;
  activeDocTitle?: string;
}

export const Header: React.FC<HeaderProps> = ({
  lang,
  onToggleLang,
  onOpenUpload,
  onOpenHistory,
  onOpenBenchmark,
  onOpenSamples,
  activeDocTitle,
}) => {
  const t = translations[lang];

  return (
    <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-md border-b border-vedic-200/80 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-20">
          {/* Brand & Title */}
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-vedic-700 via-vedic-500 to-saffron-500 p-0.5 shadow-md flex items-center justify-center">
              <div className="w-full h-full bg-vedic-900 rounded-[14px] flex items-center justify-center text-white font-bold text-2xl font-traditional">
                वा
              </div>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold font-devanagari text-vedic-950 tracking-tight">
                  {t.appTitle}
                </h1>
                <span className="hidden sm:inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  ४-चरण सत्यापित
                </span>
              </div>
              <p className="text-xs text-stone-500 hidden md:block font-devanagari">
                {t.appSubtitle}
              </p>
            </div>
          </div>

          {/* Center: Active Document Badge (if any) */}
          {activeDocTitle && (
            <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-vedic-50 border border-vedic-200 max-w-xs truncate">
              <BookOpen className="w-4 h-4 text-vedic-700 shrink-0" />
              <span className="text-xs font-medium text-vedic-900 truncate font-devanagari">
                {activeDocTitle}
              </span>
            </div>
          )}

          {/* Navigation Action Buttons */}
          <div className="flex items-center gap-2">
            <button
              onClick={onOpenUpload}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-vedic-600 to-saffron-600 hover:from-vedic-700 hover:to-saffron-700 text-white font-medium text-sm shadow-sm transition-all duration-150 transform active:scale-95 font-devanagari"
            >
              <UploadCloud className="w-4 h-4" />
              <span className="hidden sm:inline">{t.navUpload}</span>
            </button>

            <button
              onClick={onOpenHistory}
              className="inline-flex items-center gap-1.5 px-3 py-2.5 rounded-xl border border-stone-200 hover:bg-stone-50 text-stone-700 font-medium text-sm transition-colors font-devanagari"
              title={t.navHistory}
            >
              <BookOpen className="w-4 h-4 text-vedic-700" />
              <span className="hidden md:inline">{t.navHistory}</span>
            </button>

            <button
              onClick={onOpenSamples}
              className="inline-flex items-center gap-1.5 px-3 py-2.5 rounded-xl border border-stone-200 hover:bg-stone-50 text-stone-700 font-medium text-sm transition-colors font-devanagari"
              title={t.navSamples}
            >
              <Sparkles className="w-4 h-4 text-amber-600" />
              <span className="hidden md:inline">{t.navSamples}</span>
            </button>

            <button
              onClick={onOpenBenchmark}
              className="inline-flex items-center gap-1.5 px-3 py-2.5 rounded-xl border border-stone-200 hover:bg-stone-50 text-stone-700 font-medium text-sm transition-colors font-devanagari"
              title={t.navBenchmark}
            >
              <BarChart3 className="w-4 h-4 text-indigo-600" />
              <span className="hidden md:inline">{t.navBenchmark}</span>
            </button>

            {/* Language Switch Toggle */}
            <button
              onClick={onToggleLang}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-vedic-100 hover:bg-vedic-200 text-vedic-900 font-semibold text-xs border border-vedic-300 transition-colors ml-1"
            >
              <Globe2 className="w-3.5 h-3.5 text-vedic-700" />
              <span>{t.langToggle}</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
