import React, { useState, useEffect } from 'react';
import { X, Check, Edit3, AlertTriangle, ShieldCheck, Sparkles, BookOpen } from 'lucide-react';
import type { WordToken } from '../types';
import type { Language } from '../i18n/translations';
import { translations } from '../i18n/translations';

interface WordInspectorModalProps {
  token: WordToken | null;
  onClose: () => void;
  onApplyCorrection: (wordIndex: number, newText: string, reason?: string) => void;
  lang: Language;
}

export const WordInspectorModal: React.FC<WordInspectorModalProps> = ({
  token,
  onClose,
  onApplyCorrection,
  lang,
}) => {
  const t = translations[lang];
  const [manualText, setManualText] = useState<string>('');

  useEffect(() => {
    if (token) {
      setManualText(token.text);
    }
  }, [token]);

  if (!token) return null;

  const handleAcceptSuggestion = () => {
    if (token.suggested_correction) {
      onApplyCorrection(token.index, token.suggested_correction, 'accepted_ai_suggestion');
      onClose();
    }
  };

  const handleApplyManual = (e: React.FormEvent) => {
    e.preventDefault();
    if (manualText.trim() && manualText.trim() !== token.text) {
      onApplyCorrection(token.index, manualText.trim(), 'manual_user_edit');
      onClose();
    }
  };

  const isHistorical = token.is_historical_spelling;
  const hasDisagreement = Boolean(token.disagreement_type);
  const hasSuggestion = Boolean(token.suggested_correction);
  const hasAnomalies = Boolean(token.unicode_anomalies && token.unicode_anomalies.length > 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div 
        className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-stone-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-stone-100">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-vedic-100 flex items-center justify-center text-vedic-700">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-stone-900 font-devanagari">
                {t.inspectTitle}
              </h3>
              <p className="text-xs text-stone-500 font-devanagari">
                शब्द क्रमांक: {token.index + 1} | पंक्ति: {token.line_num}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-stone-400 hover:text-stone-600 hover:bg-stone-100"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Source Image Patch (Magnified Image Cutout) */}
        <div className="mt-4 p-4 rounded-2xl bg-stone-50 border border-stone-200/80">
          <div className="text-xs font-semibold text-stone-500 uppercase tracking-wider mb-2 font-devanagari">
            {t.sourcePatchTitle}
          </div>
          <div className="flex items-center justify-center p-3 bg-white rounded-xl border border-stone-200 min-h-[70px] shadow-2xs">
            {token.image_crop ? (
              <img
                src={token.image_crop}
                alt={token.text}
                className="max-h-20 object-contain rounded filter contrast-125"
              />
            ) : (
              <span className="text-xs text-stone-400 font-devanagari">
                (अंश दृश्य उपलब्ध नहीं है)
              </span>
            )}
          </div>
        </div>

        {/* Engine Readings & Comparison */}
        <div className="mt-4 grid grid-cols-2 gap-3">
          <div className="p-3 rounded-xl bg-stone-50 border border-stone-200">
            <span className="text-[11px] font-medium text-stone-500 block mb-1 font-devanagari">
              {t.primaryReading}
            </span>
            <span className="text-lg font-bold text-stone-900 font-devanagari">
              {token.original_text}
            </span>
            <span className="text-[11px] text-stone-500 block mt-0.5">
              विश्वास: {token.confidence}%
            </span>
          </div>

          <div className="p-3 rounded-xl bg-stone-50 border border-stone-200">
            <span className="text-[11px] font-medium text-stone-500 block mb-1 font-devanagari">
              {t.secondaryReading}
            </span>
            <span className="text-lg font-bold text-vedic-900 font-devanagari">
              {token.secondary_text || '—'}
            </span>
            <span className="text-[11px] text-stone-500 block mt-0.5 font-devanagari">
              {hasDisagreement ? 'भिन्नता दर्ज' : 'सहमत'}
            </span>
          </div>
        </div>

        {/* Linguistic Notes & Discrepancy Alerts */}
        <div className="mt-4 space-y-2">
          {isHistorical && (
            <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 flex items-start gap-2.5">
              <ShieldCheck className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div className="text-xs text-emerald-900 font-devanagari">
                <span className="font-bold block">प्राचीन वर्तनी संरक्षित (Historical Preserved)</span>
                {token.linguistic_note_hi || token.linguistic_note_en}
              </div>
            </div>
          )}

          {hasDisagreement && (
            <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 flex items-start gap-2.5">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div className="text-xs text-amber-900 font-devanagari">
                <span className="font-bold block">इंजन मतभेद (Engine Disagreement)</span>
                {token.discrepancy_note_hi || token.discrepancy_note_en}
              </div>
            </div>
          )}

          {hasAnomalies && token.unicode_anomalies && (
            <div className="p-3 rounded-xl bg-purple-50 border border-purple-200 flex items-start gap-2.5">
              <AlertTriangle className="w-5 h-5 text-purple-600 shrink-0 mt-0.5" />
              <div className="text-xs text-purple-900 font-devanagari">
                <span className="font-bold block">यूनिकोड/मात्रा विसंगति (Unicode Anomaly)</span>
                {token.unicode_anomalies.map((a, i) => (
                  <span key={i} className="block">{a[1]}</span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Suggestion Quick-Accept Bar */}
        {hasSuggestion && token.suggested_correction && (
          <div className="mt-4 p-3.5 rounded-2xl bg-gradient-to-r from-amber-50 to-vedic-50 border border-amber-300 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-amber-600 shrink-0" />
              <div>
                <span className="text-[11px] text-stone-500 block font-devanagari">
                  {t.suggestionLabel}
                </span>
                <span className="text-base font-bold text-vedic-950 font-devanagari">
                  {token.suggested_correction}
                </span>
              </div>
            </div>
            <button
              onClick={handleAcceptSuggestion}
              className="px-3.5 py-1.5 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-medium text-xs flex items-center gap-1.5 shadow-xs transition-colors font-devanagari"
            >
              <Check className="w-3.5 h-3.5" />
              {t.acceptSuggestion}
            </button>
          </div>
        )}

        {/* Manual Correction Form */}
        <form onSubmit={handleApplyManual} className="mt-4">
          <label className="block text-xs font-semibold text-stone-700 mb-1.5 font-devanagari">
            {t.manualCorrectionLabel}
          </label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={manualText}
              onChange={(e) => setManualText(e.target.value)}
              className="flex-1 px-4 py-2.5 rounded-xl border border-stone-300 focus:outline-none focus:ring-2 focus:ring-vedic-500 font-devanagari text-base"
              placeholder="यहाँ सही देवनागरी शब्द लिखें..."
            />
            <button
              type="submit"
              disabled={!manualText.trim() || manualText.trim() === token.text}
              className="px-4 py-2.5 rounded-xl bg-vedic-600 hover:bg-vedic-700 disabled:opacity-50 text-white font-medium text-xs flex items-center gap-1.5 transition-colors font-devanagari"
            >
              <Edit3 className="w-4 h-4" />
              {t.applyCorrection}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
