 import React, { useState } from 'react';
import { 
  Copy, Check, Edit2, ShieldCheck, AlertCircle, FileText, 
  Sparkles, CheckCircle2, ChevronRight, Filter, RotateCcw, AlertTriangle 
} from 'lucide-react';
import type { WordToken } from '../types';
import type { Language } from '../i18n/translations';
import { translations } from '../i18n/translations';

interface TextEditorProps {
  verifiedText: string;
  rawText: string;
  confirmedText?: string;
  tokens: WordToken[];
  selectedWordIndex: number | null;
  onSelectWord: (index: number) => void;
  onSaveFullText: (text: string, markConfirmed?: boolean) => void;
  verificationStatus: string;
  pageStatus?: string;
  onRetryPage?: () => void;
  lang: Language;
}

export const TextEditor: React.FC<TextEditorProps> = ({
  verifiedText,
  rawText,
  confirmedText = '',
  tokens,
  selectedWordIndex,
  onSelectWord,
  onSaveFullText,
  verificationStatus,
  pageStatus,
  onRetryPage,
  lang,
}) => {
  const t = translations[lang];
  const [viewMode, setViewMode] = useState<'reviewed' | 'raw' | 'confirmed'>('reviewed');
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editText, setEditText] = useState<string>(verifiedText);
  const [prevVerifiedText, setPrevVerifiedText] = useState<string>(verifiedText);
  const [copiedType, setCopiedType] = useState<'verified' | 'raw' | 'confirmed' | null>(null);
  const [filterFlaggedOnly, setFilterFlaggedOnly] = useState<boolean>(false);

  if (verifiedText !== prevVerifiedText) {
    setPrevVerifiedText(verifiedText);
    setEditText(verifiedText);
  }

  const hasUnsavedEdits = isEditing && editText !== verifiedText;

  const handleCopyCurrent = async () => {
    try {
      const textToCopy = viewMode === 'raw' 
        ? rawText 
        : (viewMode === 'confirmed' ? (confirmedText || verifiedText) : verifiedText);
      await navigator.clipboard.writeText(textToCopy);
      setCopiedType(viewMode as any);
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

  // Find flagged tokens indices
  const flaggedIndices = tokens
    .map((tok, idx) => {
      const isDisagreement = Boolean(tok.disagreement_type || tok.flags?.includes('DISAGREEMENT') || tok.flags?.includes('STAGE3_DISAGREEMENT'));
      const isAnomaly = Boolean((tok.unicode_anomalies && tok.unicode_anomalies.length > 0) || tok.flags?.includes('UNICODE_WARNING'));
      const isLowConf = tok.confidence < 65.0;
      return (isDisagreement || isAnomaly || isLowConf || tok.status === 'needs_review') ? idx : -1;
    })
    .filter(idx => idx !== -1);

  const handleNextUnresolved = () => {
    if (flaggedIndices.length === 0) return;
    if (selectedWordIndex === null) {
      onSelectWord(flaggedIndices[0]);
    } else {
      const nextIdx = flaggedIndices.find(idx => idx > selectedWordIndex);
      onSelectWord(nextIdx !== undefined ? nextIdx : flaggedIndices[0]);
    }
  };

  const isConfirmed = verificationStatus === 'Manually Confirmed' || pageStatus === 'Manually Confirmed';
  const isVerified = verificationStatus === 'Verified by Available Checks';
  const isFailed = pageStatus === 'FAILED';

  const displayedTokens = filterFlaggedOnly 
    ? tokens.filter((tok) => flaggedIndices.includes(tok.index))
    : tokens;

  return (
    <div className="flex flex-col h-full bg-white rounded-2xl border border-stone-200/90 overflow-hidden shadow-2xs">
      {/* Top Header & Mode Bar */}
      <div className="p-3 sm:p-4 bg-stone-50 border-b border-stone-200">
        <div className="flex flex-wrap items-center justify-between gap-2.5 mb-2.5">
          {/* Status Badge */}
          <div className="flex items-center gap-2 flex-wrap">
            {isFailed ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-100 text-rose-900 border border-rose-300 font-devanagari">
                <AlertTriangle className="w-3.5 h-3.5 text-rose-700" />
                <span>निष्कर्षण असफल (Failed)</span>
              </span>
            ) : isConfirmed ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-900 border border-blue-300 font-devanagari">
                <CheckCircle2 className="w-3.5 h-3.5 text-blue-700" />
                <span>{t.statusConfirmed}</span>
              </span>
            ) : isVerified ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-900 border border-emerald-300 font-devanagari">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-700" />
                <span>{t.statusVerified}</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-900 border border-amber-300 font-devanagari">
                <AlertCircle className="w-3.5 h-3.5 text-amber-700" />
                <span>{t.statusReview}</span>
              </span>
            )}

            {hasUnsavedEdits && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-bold bg-amber-500 text-white animate-pulse font-devanagari">
                बदलाव सहेजे नहीं गए
              </span>
            )}

            <span className="text-[11px] text-stone-500 font-devanagari">
              ({tokens.length} शब्द, {flaggedIndices.length} संदेहास्पद)
            </span>
          </div>

          {/* View Toggles & Editor Switch */}
          <div className="flex items-center gap-1.5">
            <div 
              role="group" 
              aria-label="Text view options"
              className="inline-flex rounded-lg border border-stone-200 bg-stone-100 p-0.5 text-xs font-devanagari"
            >
              <button
                type="button"
                onClick={() => { setViewMode('reviewed'); setIsEditing(false); }}
                className={`px-2 py-1 rounded-md transition-all text-xs ${
                  viewMode === 'reviewed' ? 'bg-white font-bold text-stone-900 shadow-2xs' : 'text-stone-600 hover:text-stone-900'
                }`}
                aria-pressed={viewMode === 'reviewed'}
              >
                समीक्षित
              </button>
              <button
                type="button"
                onClick={() => { setViewMode('raw'); setIsEditing(false); }}
                className={`px-2 py-1 rounded-md transition-all text-xs ${
                  viewMode === 'raw' ? 'bg-white font-bold text-stone-900 shadow-2xs' : 'text-stone-600 hover:text-stone-900'
                }`}
                aria-pressed={viewMode === 'raw'}
              >
                मूल OCR
              </button>
              <button
                type="button"
                onClick={() => { setViewMode('confirmed'); setIsEditing(false); }}
                className={`px-2 py-1 rounded-md transition-all text-xs ${
                  viewMode === 'confirmed' ? 'bg-white font-bold text-stone-900 shadow-2xs' : 'text-stone-600 hover:text-stone-900'
                }`}
                aria-pressed={viewMode === 'confirmed'}
              >
                पुष्ट
              </button>
            </div>

            <button
              type="button"
              onClick={() => setIsEditing(!isEditing)}
              className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border text-xs font-medium font-devanagari transition-colors ${
                isEditing
                  ? 'bg-vedic-700 text-white border-vedic-700 shadow-2xs'
                  : 'bg-white text-stone-700 border-stone-200 hover:bg-stone-50'
              }`}
              aria-pressed={isEditing}
            >
              <Edit2 className="w-3.5 h-3.5" />
              <span>{isEditing ? 'दृश्य' : 'संपादन'}</span>
            </button>
          </div>
        </div>

        {/* Action Controls Bar */}
        <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
          {/* Primary Copy Button */}
          <button
            type="button"
            onClick={handleCopyCurrent}
            className="flex-1 min-w-[140px] inline-flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 active:bg-emerald-900 text-white font-semibold text-xs shadow-2xs transition-colors font-devanagari"
            aria-label={t.copyVerifiedText}
          >
            {copiedType ? (
              <>
                <Check className="w-3.5 h-3.5 text-white" />
                <span>कॉपी हो गया! (Copied)</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>{t.copyVerifiedText}</span>
              </>
            )}
          </button>

          {/* Copy Raw Button */}
          <button
            type="button"
            onClick={handleCopyRaw}
            className="inline-flex items-center gap-1 px-2.5 py-2 rounded-xl border border-stone-200 bg-white hover:bg-stone-50 text-stone-700 text-xs font-medium transition-colors font-devanagari"
            title={t.copyRawText}
            aria-label={t.copyRawText}
          >
            <FileText className="w-3.5 h-3.5 text-stone-500" />
            <span className="hidden sm:inline">मूल OCR</span>
          </button>

          {/* Jump to Next Unresolved */}
          {flaggedIndices.length > 0 && (
            <button
              type="button"
              onClick={handleNextUnresolved}
              className="inline-flex items-center gap-1 px-2.5 py-2 rounded-xl border border-amber-300 bg-amber-50 hover:bg-amber-100 text-amber-900 text-xs font-semibold transition-colors font-devanagari"
              title="अगले संदेहास्पद शब्द पर जाएँ"
              aria-label="अगले संदेहास्पद शब्द पर जाएँ"
            >
              <span>अगला संदेहास्पद</span>
              <ChevronRight className="w-3.5 h-3.5 text-amber-700" />
            </button>
          )}

          {/* Filter Flagged Toggle */}
          <button
            type="button"
            onClick={() => setFilterFlaggedOnly(!filterFlaggedOnly)}
            className={`inline-flex items-center gap-1 px-2.5 py-2 rounded-xl border text-xs font-medium transition-colors font-devanagari ${
              filterFlaggedOnly
                ? 'bg-purple-100 border-purple-300 text-purple-900 font-bold'
                : 'bg-white border-stone-200 text-stone-700 hover:bg-stone-50'
            }`}
            title="केवल संदेहास्पद शब्द देखें"
            aria-pressed={filterFlaggedOnly}
          >
            <Filter className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">{filterFlaggedOnly ? 'सभी शब्द' : 'केवल ध्वजांकित'}</span>
          </button>

          {/* Retry Button if page failed */}
          {isFailed && onRetryPage && (
            <button
              type="button"
              onClick={onRetryPage}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold font-devanagari transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>पुनः प्रयास करें</span>
            </button>
          )}
        </div>
      </div>

      {/* Editor Main Content Area */}
      <div className="flex-1 p-3 sm:p-5 overflow-auto bg-parchment-50/40">
        {isEditing ? (
          /* Direct Full Text Editing Area */
          <div className="h-full flex flex-col gap-3">
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              className="flex-1 w-full p-3 sm:p-4 rounded-xl border border-stone-300 focus:outline-none focus:ring-2 focus:ring-vedic-500 font-devanagari text-base sm:text-lg leading-[2.2] bg-white resize-none shadow-2xs"
              placeholder="यहाँ देवनागरी पाठ संपादित करें..."
              aria-label="देवनागरी पाठ संपादन क्षेत्र"
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs text-stone-500 font-devanagari">
                {hasUnsavedEdits ? '⚠️ बदलाव अभी सहेजे नहीं गए हैं।' : '✓ पाठ सुरक्षित है।'}
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleSaveText(false)}
                  className="px-3.5 py-2 rounded-xl bg-stone-200 hover:bg-stone-300 text-stone-800 text-xs font-semibold font-devanagari transition-colors"
                >
                  {t.saveChanges}
                </button>
                <button
                  type="button"
                  onClick={() => handleSaveText(true)}
                  className="px-3.5 py-2 rounded-xl bg-vedic-700 hover:bg-vedic-800 text-white text-xs font-semibold font-devanagari shadow-2xs transition-colors"
                >
                  {t.markConfirmed}
                </button>
              </div>
            </div>
          </div>
        ) : viewMode === 'raw' ? (
          /* Raw OCR View */
          <div className="p-4 bg-white rounded-xl border border-stone-200 font-devanagari text-base sm:text-lg leading-[2.2] whitespace-pre-wrap text-stone-800 select-text shadow-2xs">
            <div className="mb-2 text-xs font-bold text-stone-400 uppercase tracking-wider font-sans">
              मूल प्राथमिक टेसरेक्ट OCR पाठ (अपरिवर्तित):
            </div>
            {rawText || '(कोई मूल OCR पाठ उपलब्ध नहीं है)'}
          </div>
        ) : viewMode === 'confirmed' ? (
          /* Confirmed Text View */
          <div className="p-4 bg-white rounded-xl border border-blue-200 font-devanagari text-base sm:text-lg leading-[2.2] whitespace-pre-wrap text-stone-900 select-text shadow-2xs">
            <div className="mb-2 text-xs font-bold text-blue-700 uppercase tracking-wider font-sans">
              मानवीय रूप से प्रमाणित पाठ (Manually Confirmed):
            </div>
            {confirmedText || verifiedText || '(अभी तक कोई पुष्ट पाठ उपलब्ध नहीं है)'}
          </div>
        ) : (
          /* Interactive Word-by-Word Highlighted View */
          <div className="p-3 sm:p-5 bg-white rounded-xl border border-stone-200/90 shadow-2xs min-h-full">
            <div className="font-devanagari text-base sm:text-lg leading-[2.3] tracking-wide flex flex-wrap gap-x-2 gap-y-2.5 items-baseline">
              {displayedTokens.map((tok) => {
                const isSelected = selectedWordIndex === tok.index;
                const isHistorical = tok.is_historical_spelling || tok.flags?.includes('HISTORICAL_WORD_PRESERVED');
                const isDisagreement = Boolean(tok.disagreement_type || tok.flags?.includes('DISAGREEMENT') || tok.flags?.includes('STAGE3_DISAGREEMENT'));
                const isAnomaly = Boolean((tok.unicode_anomalies && tok.unicode_anomalies.length > 0) || tok.flags?.includes('UNICODE_WARNING'));
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
                  chipStyle += ' ring-2 ring-vedic-600 bg-vedic-100 text-vedic-950 font-bold';
                }

                return (
                  <button
                    key={`word-${tok.index}`}
                    type="button"
                    onClick={() => onSelectWord(tok.index)}
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-lg border text-base sm:text-lg cursor-pointer transition-all duration-100 ${chipStyle}`}
                    title={`विश्वास: ${tok.confidence}% | क्लिक कर संवीक्षा करें`}
                    aria-label={`${tok.text}, विश्वास ${tok.confidence} प्रतिशत`}
                  >
                    <span>{tok.text}</span>
                    {tok.suggested_correction && (
                      <Sparkles className="w-3 h-3 text-amber-600 inline shrink-0" />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Editor Footer / Quick Instruction */}
      <div className="px-3 sm:px-4 py-2 bg-stone-50 border-t border-stone-200 text-[11px] sm:text-xs text-stone-500 flex items-center justify-between font-devanagari">
        <span className="truncate">
          💡 किसी भी शब्द पर क्लिक करके मूल पाण्डुलिपि से आवर्धित मिलान एवं सुधार करें
        </span>
        <span className="font-mono text-[10px] text-stone-400 shrink-0 ml-2">
          UTF-8 Devanagari
        </span>
      </div>
    </div>
  );
};
