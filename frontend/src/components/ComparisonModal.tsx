import React, { useState, useEffect } from 'react';
import { 
  X, GitCompare, Zap, Check, Copy, 
  RefreshCw, AlertCircle, CheckCircle2, SplitSquareVertical, Play
} from 'lucide-react';
import type { Language } from '../i18n/translations';
import { translations } from '../i18n/translations';
import type { ComparisonData, WordDiffItem } from '../types';
import { api } from '../services/api';

interface ComparisonModalProps {
  isOpen: boolean;
  onClose: () => void;
  documentId: string;
  pageNumber: number;
  originalImageUrl?: string;
  initialComparison?: ComparisonData | null;
  lang: Language;
  onSelectEngineSuccess?: () => Promise<void> | void;
}

export const hasValidComparison = (comp: any): comp is ComparisonData => {
  return Boolean(
    comp &&
    typeof comp === 'object' &&
    comp.summary &&
    typeof comp.summary === 'object' &&
    comp.tesseract &&
    typeof comp.tesseract === 'object' &&
    comp.easyocr &&
    typeof comp.easyocr === 'object'
  );
};

export const ComparisonModal: React.FC<ComparisonModalProps> = ({
  isOpen,
  onClose,
  documentId,
  pageNumber,
  originalImageUrl: _originalImageUrl,
  initialComparison,
  lang,
  onSelectEngineSuccess
}) => {
  const t = translations[lang];
  const [comparison, setComparison] = useState<ComparisonData | null>(
    initialComparison && hasValidComparison(initialComparison) ? initialComparison : null
  );
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedEngine, setCopiedEngine] = useState<string | null>(null);
  const [isApplyingSelection, setIsApplyingSelection] = useState<boolean>(false);
  const [selectedEngineNotice, setSelectedEngineNotice] = useState<string | null>(null);

  // Keyboard accessibility
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !isLoading && !isApplyingSelection) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isLoading, isApplyingSelection, onClose]);

  // Load comparison data when modal opens or document/page changes
  useEffect(() => {
    if (!isOpen) {
      setError(null);
      return;
    }

    if (initialComparison && hasValidComparison(initialComparison)) {
      setComparison(initialComparison);
      setIsLoading(false);
      return;
    }

    let isMounted = true;

    const fetchExistingOrRun = async () => {
      try {
        setIsLoading(true);
        setError(null);
        setComparison(null);

        const res = await api.getPageComparison(documentId, pageNumber);
        if (!isMounted) return;

        if (res.has_comparison && hasValidComparison(res.comparison)) {
          setComparison(res.comparison);
        } else {
          // If never run, run comparison now
          const compRes = await api.comparePageOcr(documentId, pageNumber);
          if (!isMounted) return;

          if (hasValidComparison(compRes)) {
            setComparison(compRes);
          } else {
            setError('तुलना परिणाम प्राप्त करने में त्रुटि हुई।');
          }
        }
      } catch (err: any) {
        if (!isMounted) return;
        setError(err.message || 'तुलना निष्पादित करने में त्रुटि हुई।');
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchExistingOrRun();

    return () => {
      isMounted = false;
    };
  }, [isOpen, documentId, pageNumber, initialComparison]);

  if (!isOpen) return null;

  const handleRunComparison = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await api.comparePageOcr(documentId, pageNumber);
      if (hasValidComparison(res)) {
        setComparison(res);
      } else {
        setError('तुलना परिणाम मान्य नहीं है।');
      }
    } catch (err: any) {
      setError(err.message || 'तुलना निष्पादित करने में त्रुटि हुई।');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = (text: string, engineName: string) => {
    navigator.clipboard.writeText(text);
    setCopiedEngine(engineName);
    setTimeout(() => setCopiedEngine(null), 2000);
  };

  const handleSelectEngine = async (engine: 'tesseract' | 'easyocr', text: string) => {
    try {
      setIsApplyingSelection(true);
      setError(null);
      await api.selectPreferredEngine(documentId, pageNumber, engine, text);
      setSelectedEngineNotice(engine === 'tesseract' ? 'Tesseract' : 'EasyOCR');
      if (onSelectEngineSuccess) {
        await onSelectEngineSuccess();
      }
      setTimeout(() => {
        setSelectedEngineNotice(null);
        onClose();
      }, 1000);
    } catch (err: any) {
      setError(err.message || 'इंजन पाठ लागू करने में त्रुटि हुई।');
    } finally {
      setIsApplyingSelection(false);
    }
  };

  const isComparisonReady = hasValidComparison(comparison);

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-stone-950/75 backdrop-blur-xs animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="comparison-modal-title"
    >
      <div className="bg-white rounded-2xl max-w-6xl w-full max-h-[92vh] flex flex-col shadow-2xl border border-stone-200 overflow-hidden">
        {/* Header */}
        <div className="px-4 sm:px-6 py-3.5 border-b border-stone-200 flex items-center justify-between bg-stone-50/90 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-vedic-100 border border-vedic-200/80 text-vedic-800 flex items-center justify-center shadow-2xs shrink-0">
              <GitCompare className="w-5 h-5 text-vedic-700" />
            </div>
            <div>
              <h2 id="comparison-modal-title" className="text-base sm:text-lg font-bold text-stone-900 font-devanagari flex items-center gap-2">
                <span>{t.comparisonModalTitle}</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-stone-200 text-stone-700 font-sans font-medium">
                  Page {pageNumber}
                </span>
              </h2>
              <p className="text-xs text-stone-500 font-devanagari">
                {t.comparisonModalDesc}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleRunComparison}
              disabled={isLoading || isApplyingSelection}
              className="px-3 py-1.5 rounded-xl border border-stone-300 bg-white hover:bg-stone-100 disabled:opacity-50 text-xs font-semibold text-stone-700 flex items-center gap-1.5 transition-colors font-devanagari"
              title="पुनः तुलना निष्पादित करें"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-vedic-600' : ''}`} />
              <span className="hidden sm:inline">पुनः जाँचें</span>
            </button>

            <button
              type="button"
              onClick={onClose}
              disabled={isLoading || isApplyingSelection}
              className="p-1.5 text-stone-400 hover:text-stone-700 hover:bg-stone-200/60 rounded-xl transition-colors"
              aria-label={t.close}
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Status Notice Banners */}
        {error && (
          <div className="mx-4 sm:mx-6 mt-4 p-3 bg-red-50 border border-red-200 rounded-xl flex items-center gap-2.5 text-xs text-red-700 font-devanagari">
            <AlertCircle className="w-4 h-4 text-red-500 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {selectedEngineNotice && (
          <div className="mx-4 sm:mx-6 mt-4 p-3 bg-emerald-50 border border-emerald-200 rounded-xl flex items-center gap-2.5 text-xs text-emerald-800 font-devanagari">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>
              <strong>{selectedEngineNotice}</strong> का पाठ इस पृष्ठ के सक्रिय पाठ के रूप में सुरक्षित कर लिया गया है।
            </span>
          </div>
        )}

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-3 sm:p-6 space-y-4 font-devanagari">
          {isLoading && !isComparisonReady ? (
            <div className="py-20 flex flex-col items-center justify-center text-center">
              <RefreshCw className="w-8 h-8 text-vedic-600 animate-spin mb-3" />
              <span className="font-semibold text-stone-800 text-sm">
                Tesseract एवं EasyOCR दोनों निष्पादित हो रहे हैं...
              </span>
              <span className="text-xs text-stone-500 mt-1">
                (देवनागरी पाठ, मात्राओं एवं गति का तुलनात्मक विश्लेषण जारी है)
              </span>
            </div>
          ) : isComparisonReady && comparison ? (
            <>
              {/* Summary Stats Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {/* Similarity Ratio */}
                <div className="bg-stone-50 border border-stone-200 rounded-xl p-3 flex flex-col">
                  <span className="text-[11px] text-stone-500 font-medium">{t.similarityLabel}</span>
                  <div className="text-lg font-bold text-stone-900 mt-0.5 font-mono">
                    {comparison.similarity_ratio ?? 0}%
                  </div>
                  <span className="text-[10px] text-stone-400 mt-0.5">दोनों इंजनों के पाठ में सादृश्य</span>
                </div>

                {/* Speedup Factor */}
                <div className="bg-amber-50/60 border border-amber-200/80 rounded-xl p-3 flex flex-col">
                  <span className="text-[11px] text-amber-900 font-medium">{t.fasterLabel}</span>
                  <div className="text-lg font-bold text-amber-950 mt-0.5 capitalize flex items-center gap-1 font-sans">
                    <Zap className="w-4 h-4 text-amber-600 shrink-0" />
                    {comparison.summary?.faster_engine || 'Tesseract'}
                  </div>
                  <span className="text-[10px] text-amber-700 font-mono mt-0.5">
                    {comparison.summary?.speedup_factor ?? 1}x faster ({
                      (comparison.summary?.tesseract_time_ms ?? 0) < (comparison.summary?.easyocr_time_ms ?? 0)
                        ? `${((comparison.summary?.tesseract_time_ms ?? 0) / 1000).toFixed(2)}s vs ${((comparison.summary?.easyocr_time_ms ?? 0) / 1000).toFixed(2)}s`
                        : `${((comparison.summary?.easyocr_time_ms ?? 0) / 1000).toFixed(2)}s vs ${((comparison.summary?.tesseract_time_ms ?? 0) / 1000).toFixed(2)}s`
                    })
                  </span>
                </div>

                {/* Tesseract Speed */}
                <div className="bg-blue-50/60 border border-blue-200/80 rounded-xl p-3 flex flex-col">
                  <span className="text-[11px] text-blue-900 font-medium">Tesseract समय:</span>
                  <div className="text-lg font-bold text-blue-950 mt-0.5 font-mono">
                    {((comparison.tesseract?.processing_time_ms ?? 0) / 1000).toFixed(2)}s
                  </div>
                  <span className="text-[10px] text-blue-700 mt-0.5">
                    {comparison.tesseract?.word_count ?? 0} शब्द ({comparison.tesseract?.char_count ?? 0} वर्ण)
                  </span>
                </div>

                {/* EasyOCR Speed */}
                <div className="bg-purple-50/60 border border-purple-200/80 rounded-xl p-3 flex flex-col">
                  <span className="text-[11px] text-purple-900 font-medium">EasyOCR समय:</span>
                  <div className="text-lg font-bold text-purple-950 mt-0.5 font-mono">
                    {((comparison.easyocr?.processing_time_ms ?? 0) / 1000).toFixed(2)}s
                  </div>
                  <span className="text-[10px] text-purple-700 mt-0.5">
                    {comparison.easyocr?.word_count ?? 0} शब्द ({comparison.easyocr?.char_count ?? 0} वर्ण)
                  </span>
                </div>
              </div>

              {/* Side-by-Side Dual Extraction Panels */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Left Panel: Tesseract */}
                <div className="border border-blue-200 bg-blue-50/30 rounded-2xl p-4 flex flex-col">
                  <div className="flex items-center justify-between pb-3 border-b border-blue-200/80">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full bg-blue-600" />
                      <span className="font-bold text-sm text-blue-950 font-sans">
                        Tesseract LSTM (hin+san)
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => handleCopy(comparison.tesseract?.text || '', 'tesseract')}
                        className="px-2.5 py-1 rounded-lg border border-blue-200 bg-white hover:bg-blue-50 text-blue-800 text-xs font-semibold flex items-center gap-1 transition-colors"
                        title={t.copyTesseract}
                      >
                        {copiedEngine === 'tesseract' ? (
                          <>
                            <Check className="w-3 h-3 text-emerald-600" />
                            <span className="text-emerald-700">कॉपी हुआ!</span>
                          </>
                        ) : (
                          <>
                            <Copy className="w-3 h-3" />
                            <span>{t.copyTesseract}</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Text Content */}
                  <div className="flex-1 my-3 bg-white border border-blue-100 rounded-xl p-3.5 font-devanagari text-stone-900 text-sm leading-relaxed whitespace-pre-wrap max-h-60 overflow-y-auto select-text shadow-2xs">
                    {comparison.tesseract?.text || (
                      <span className="text-stone-400 italic">कोई पाठ नहीं मिला</span>
                    )}
                  </div>

                  {/* Bottom Panel Actions */}
                  <div className="pt-2 flex items-center justify-between border-t border-blue-200/60 text-xs">
                    <span className="text-blue-900 font-mono text-[11px]">
                      {comparison.tesseract?.char_count ?? 0} वर्ण • {comparison.tesseract?.word_count ?? 0} शब्द
                    </span>
                    <button
                      type="button"
                      onClick={() => handleSelectEngine('tesseract', comparison.tesseract?.text || '')}
                      disabled={isApplyingSelection || !comparison.tesseract?.text}
                      className="px-3.5 py-1.5 rounded-xl bg-blue-700 hover:bg-blue-800 disabled:opacity-50 text-white font-bold text-xs shadow-xs transition-colors flex items-center gap-1.5 font-devanagari cursor-pointer"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>{t.useTesseractBtn}</span>
                    </button>
                  </div>
                </div>

                {/* Right Panel: EasyOCR */}
                <div className="border border-purple-200 bg-purple-50/30 rounded-2xl p-4 flex flex-col">
                  <div className="flex items-center justify-between pb-3 border-b border-purple-200/80">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full bg-purple-600" />
                      <span className="font-bold text-sm text-purple-950 font-sans">
                        EasyOCR Devanagari (CRAFT)
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => handleCopy(comparison.easyocr?.text || '', 'easyocr')}
                        className="px-2.5 py-1 rounded-lg border border-purple-200 bg-white hover:bg-purple-50 text-purple-800 text-xs font-semibold flex items-center gap-1 transition-colors"
                        title={t.copyEasyOcr}
                      >
                        {copiedEngine === 'easyocr' ? (
                          <>
                            <Check className="w-3 h-3 text-emerald-600" />
                            <span className="text-emerald-700">कॉपी हुआ!</span>
                          </>
                        ) : (
                          <>
                            <Copy className="w-3 h-3" />
                            <span>{t.copyEasyOcr}</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Text Content */}
                  <div className="flex-1 my-3 bg-white border border-purple-100 rounded-xl p-3.5 font-devanagari text-stone-900 text-sm leading-relaxed whitespace-pre-wrap max-h-60 overflow-y-auto select-text shadow-2xs">
                    {comparison.easyocr?.text || (
                      <span className="text-stone-400 italic">कोई पाठ नहीं मिला</span>
                    )}
                  </div>

                  {/* Bottom Panel Actions */}
                  <div className="pt-2 flex items-center justify-between border-t border-purple-200/60 text-xs">
                    <span className="text-purple-900 font-mono text-[11px]">
                      {comparison.easyocr?.char_count ?? 0} वर्ण • {comparison.easyocr?.word_count ?? 0} शब्द
                    </span>
                    <button
                      type="button"
                      onClick={() => handleSelectEngine('easyocr', comparison.easyocr?.text || '')}
                      disabled={isApplyingSelection || !comparison.easyocr?.text}
                      className="px-3.5 py-1.5 rounded-xl bg-purple-700 hover:bg-purple-800 disabled:opacity-50 text-white font-bold text-xs shadow-xs transition-colors flex items-center gap-1.5 font-devanagari cursor-pointer"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>{t.useEasyOcrBtn}</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Visual Diff Discrepancy Inspector */}
              <div className="border border-stone-200 rounded-2xl p-4 bg-stone-50/70">
                <div className="flex items-center justify-between mb-3 pb-2 border-b border-stone-200">
                  <div className="flex items-center gap-2">
                    <SplitSquareVertical className="w-4 h-4 text-stone-600" />
                    <span className="font-bold text-xs sm:text-sm text-stone-800">
                      {t.visualDiffTitle}
                    </span>
                  </div>
                  <div className="text-[11px] text-stone-500 font-mono">
                    {comparison.diff?.exact_matches_count ?? 0} समान खंड • {comparison.diff?.differing_blocks_count ?? 0} भिन्न खंड
                  </div>
                </div>

                <div className="space-y-1.5 max-h-48 overflow-y-auto p-1">
                  {(comparison.diff?.word_diffs || []).map((diff: WordDiffItem, dIdx: number) => {
                    if (diff.tag === 'equal') {
                      return (
                        <div key={dIdx} className="text-xs text-stone-700 bg-white px-2.5 py-1 rounded-lg border border-stone-100 font-mono flex items-center gap-2">
                          <span className="text-[10px] text-stone-400 select-none">✓</span>
                          <span>{diff.tesseract_text}</span>
                        </div>
                      );
                    }
                    return (
                      <div key={dIdx} className="text-xs bg-amber-50/80 border border-amber-200/70 rounded-xl p-2.5 grid grid-cols-1 sm:grid-cols-2 gap-2">
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] font-bold text-blue-700 bg-blue-100 px-1.5 py-0.5 rounded uppercase">
                            Tesseract
                          </span>
                          <span className="text-stone-900 font-semibold">{diff.tesseract_text || '(खाली)'}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] font-bold text-purple-700 bg-purple-100 px-1.5 py-0.5 rounded uppercase">
                            EasyOCR
                          </span>
                          <span className="text-stone-900 font-semibold">{diff.easyocr_text || '(खाली)'}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          ) : (
            <div className="py-16 flex flex-col items-center justify-center text-center">
              <div className="w-12 h-12 rounded-2xl bg-stone-100 border border-stone-200 flex items-center justify-center text-stone-500 mb-3">
                <GitCompare className="w-6 h-6" />
              </div>
              <h3 className="font-bold text-stone-800 text-sm">
                इस पृष्ठ पर अभी OCR इंजन तुलना नहीं की गई है
              </h3>
              <p className="text-xs text-stone-500 max-w-sm mt-1">
                Tesseract और EasyOCR दोनों को एक साथ चलाकर उनके देवनागरी पाठ, मात्राओं एवं गति की निष्पक्ष तुलना करें।
              </p>
              <button
                type="button"
                onClick={handleRunComparison}
                disabled={isLoading}
                className="mt-4 px-4 py-2 rounded-xl bg-vedic-700 hover:bg-vedic-800 text-white font-bold text-xs flex items-center gap-2 shadow-sm transition-all"
              >
                <Play className="w-3.5 h-3.5" />
                <span>तुलना शुरू करें</span>
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 sm:px-6 py-3 border-t border-stone-200 bg-stone-50 flex items-center justify-between shrink-0 font-devanagari">
          <div className="text-xs text-stone-500">
            💡 चुने गए इंजन का पाठ सत्यापन संपादक में स्वतः लोड होगा और ५-चरणीय संवीक्षा से गुजरेगा।
          </div>

          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-xl border border-stone-300 bg-white hover:bg-stone-100 font-semibold text-xs text-stone-700 transition-colors cursor-pointer"
          >
            {t.close}
          </button>
        </div>
      </div>
    </div>
  );
};
