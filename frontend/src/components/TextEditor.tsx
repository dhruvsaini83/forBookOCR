import React, { useState, useEffect } from 'react';
import { Copy, Check, Edit2, ShieldCheck, AlertCircle, FileText, Sparkles, CheckCircle2 } from 'lucide-react';
import type { WordToken } from '../types';
import type { Language } from '../i18n/translations';
import { translations } from '../i18n/translations';

interface TextEditorProps {
  verifiedText: string;
  rawText: string;
  tokens: WordToken[];
  selectedWordIndex: number | null;
  onSelectWord: (index: number) => void;
  onSaveFullText: (text: string, markConfirmed?: boolean) => void;
  verificationStatus: string;
  lang: Language;
}

export const TextEditor: React.FC<TextEditorProps> = ({
  verifiedText,
  rawText,
  tokens,
  selectedWordIndex,
  onSelectWord,
  onSaveFullText,
  verificationStatus,
  lang,
}) => {
  const t = translations[lang];
  const [isRawMode, setIsRawMode] = useState<boolean>(false);
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editText, setEditText] = useState<string>(verifiedText);
  const [copiedType, setCopiedType] = useState<'verified' | 'raw' | null>(null);

  useEffect(() => {
    setEditText(verifiedText);
  }, [verifiedText]);

  const handleCopyVerified = async () => {
    try {
      await navigator.clipboard.writeText(verifiedText);
      setCopiedType('verified');
      setTimeout(() => setCopiedType(null), 2500);
    } catch (e) {
      console.error('Failed to copy', e);
    }
  };

  const handleCopyRaw = async () => {
    try {
      await navigator.clipboard.writeText(rawText);
      setCopiedType('raw');
      setTimeout(() => setCopiedType(null), 2500);
    } catch (e) {
      console.error('Failed to copy', e);
    }
  };

  const handleSaveText = (confirm = false) => {
    onSaveFullText(editText, confirm);
    setIsEditing(false);
  };

  const isConfirmed = verificationStatus === 'Manually Confirmed';
  const isVerified = verificationStatus === 'Verified by Available Checks';

  return (
    <div className="flex flex-col h-full bg-white rounded-2xl border border-stone-200 overflow-hidden shadow-sm">
      {/* Top Header & Copy Bar */}
      <div className="p-4 bg-stone-50 border-b border-stone-200">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          {/* Status Badge */}
          <div className="flex items-center gap-2">
            {isConfirmed ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-900 border border-blue-300 font-devanagari">
                <CheckCircle2 className="w-3.5 h-3.5 text-blue-700" />
                {t.statusConfirmed}
              </span>
            ) : isVerified ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-900 border border-emerald-300 font-devanagari">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-700" />
                {t.statusVerified}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-900 border border-amber-300 font-devanagari">
                <AlertCircle className="w-3.5 h-3.5 text-amber-700" />
                {t.statusReview}
              </span>
            )}
            <span className="text-xs text-stone-500 font-devanagari">
              ({tokens.length} शब्द)
            </span>
          </div>

          {/* View Toggles & Editor Switch */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsRawMode(!isRawMode)}
              className="px-2.5 py-1 rounded-lg border border-stone-200 bg-white text-stone-600 hover:text-stone-900 text-xs font-medium font-devanagari"
            >
              {isRawMode ? 'सत्यापित दृश्य' : 'मूल OCR दृश्य'}
            </button>
            <button
              onClick={() => setIsEditing(!isEditing)}
              className={`inline-flex items-center gap-1 px-3 py-1 rounded-lg border text-xs font-medium font-devanagari transition-colors ${
                isEditing
                  ? 'bg-vedic-600 text-white border-vedic-600'
                  : 'bg-white text-stone-700 border-stone-200 hover:bg-stone-50'
              }`}
            >
              <Edit2 className="w-3.5 h-3.5" />
              <span>{isEditing ? 'संपादन पूर्ण' : 'सीधा संपादन'}</span>
            </button>
          </div>
        </div>

        {/* Copy Buttons Bar */}
        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={handleCopyVerified}
            className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white font-semibold text-sm shadow-xs transition-all active:scale-98 font-devanagari"
          >
            {copiedType === 'verified' ? (
              <>
                <Check className="w-4 h-4 text-white" />
                <span>कॉपी हो गया! (Copied)</span>
              </>
            ) : (
              <>
                <Copy className="w-4 h-4" />
                <span>{t.copyVerifiedText}</span>
              </>
            )}
          </button>

          <button
            onClick={handleCopyRaw}
            className="inline-flex items-center gap-1.5 px-3 py-2.5 rounded-xl border border-stone-200 bg-white hover:bg-stone-50 text-stone-700 text-xs font-medium transition-colors font-devanagari"
            title={t.copyRawText}
          >
            {copiedType === 'raw' ? (
              <Check className="w-3.5 h-3.5 text-emerald-600" />
            ) : (
              <FileText className="w-3.5 h-3.5 text-stone-500" />
            )}
            <span className="hidden sm:inline">{t.copyRawText}</span>
          </button>
        </div>
      </div>

      {/* Editor Main Content Area */}
      <div className="flex-1 p-6 overflow-auto bg-parchment-50/40">
        {isEditing ? (
          /* Direct Full Text Editing Area */
          <div className="h-full flex flex-col gap-3">
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              className="flex-1 w-full p-4 rounded-xl border border-stone-300 focus:outline-none focus:ring-2 focus:ring-vedic-500 font-devanagari text-lg leading-relaxed bg-white resize-none"
              placeholder="यहाँ देवनागरी पाठ संपादित करें..."
            />
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => handleSaveText(false)}
                className="px-4 py-2 rounded-xl bg-stone-200 hover:bg-stone-300 text-stone-800 text-xs font-semibold font-devanagari"
              >
                {t.saveChanges}
              </button>
              <button
                onClick={() => handleSaveText(true)}
                className="px-4 py-2 rounded-xl bg-vedic-600 hover:bg-vedic-700 text-white text-xs font-semibold font-devanagari"
              >
                {t.markConfirmed}
              </button>
            </div>
          </div>
        ) : isRawMode ? (
          /* Raw OCR View */
          <div className="p-4 bg-white rounded-xl border border-stone-200 font-devanagari text-base leading-loose whitespace-pre-wrap text-stone-700 select-text">
            {rawText || '(कोई मूल OCR पाठ उपलब्ध नहीं है)'}
          </div>
        ) : (
          /* Interactive Word-by-Word Highlighted View */
          <div className="p-4 bg-white rounded-xl border border-stone-200/90 shadow-2xs min-h-full">
            <div className="font-devanagari text-lg leading-loose tracking-wide flex flex-wrap gap-x-2 gap-y-2.5 items-baseline">
              {tokens.map((tok) => {
                const isSelected = selectedWordIndex === tok.index;
                const isHistorical = tok.is_historical_spelling;
                const isDisagreement = Boolean(tok.disagreement_type);
                const isAnomaly = Boolean(tok.unicode_anomalies && tok.unicode_anomalies.length > 0);
                const isLowConf = tok.confidence < 65.0;

                let chipStyle = 'bg-stone-50 border-stone-200 text-stone-800 hover:bg-stone-100';

                if (isDisagreement) {
                  chipStyle = 'bg-amber-50 border-amber-300 text-amber-950 font-medium hover:bg-amber-100 ring-1 ring-amber-300';
                } else if (isAnomaly) {
                  chipStyle = 'bg-purple-50 border-purple-300 text-purple-950 font-medium hover:bg-purple-100 ring-1 ring-purple-300';
                } else if (isHistorical) {
                  chipStyle = 'bg-emerald-50 border-emerald-300 text-emerald-950 font-medium hover:bg-emerald-100';
                } else if (isLowConf) {
                  chipStyle = 'bg-rose-50 border-rose-300 text-rose-950 font-medium hover:bg-rose-100';
                }

                if (isSelected) {
                  chipStyle += ' ring-2 ring-vedic-600 bg-vedic-100/80';
                }

                return (
                  <button
                    key={`word-${tok.index}`}
                    onClick={() => onSelectWord(tok.index)}
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-lg border text-base cursor-pointer transition-all duration-100 ${chipStyle}`}
                    title={`विश्वास: ${tok.confidence}% | क्लिक कर संवीक्षा करें`}
                  >
                    <span>{tok.text}</span>
                    {tok.suggested_correction && (
                      <Sparkles className="w-3 h-3 text-amber-600 inline" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Editor Footer / Quick Instruction */}
      <div className="px-4 py-2.5 bg-stone-50 border-t border-stone-200 text-xs text-stone-500 flex items-center justify-between font-devanagari">
        <span>
          💡 किसी भी शब्द पर क्लिक करके मूल पाण्डुलिपि से आवर्धित मिलान एवं सुधार करें
        </span>
        <span className="font-mono text-[11px] text-stone-400">
          यूनिकोड देवनागरी (UTF-8)
        </span>
      </div>
    </div>
  );
};
