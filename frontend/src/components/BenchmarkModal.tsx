import React, { useState, useEffect } from 'react';
import { X, BarChart3, ArrowRight, RefreshCw } from 'lucide-react';
import type { BenchmarkCase } from '../types';
import type { Language } from '../i18n/translations';
import { translations } from '../i18n/translations';
import { api } from '../services/api';

interface BenchmarkModalProps {
  isOpen: boolean;
  onClose: () => void;
  lang: Language;
}

export const BenchmarkModal: React.FC<BenchmarkModalProps> = ({
  isOpen,
  onClose,
  lang,
}) => {
  const t = translations[lang];
  const [cases, setCases] = useState<BenchmarkCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string>('ramcharitmanas_doha');
  const [testText, setTestText] = useState<string>('');
  const [evalResult, setEvalResult] = useState<any>(null);
  const [isEvaluating, setIsEvaluating] = useState<boolean>(false);

  // Escape key closes modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  useEffect(() => {
    if (isOpen) {
      api.getBenchmarks().then((res) => {
        setCases(res.benchmarks);
        if (res.benchmarks.length > 0) {
          setSelectedCaseId(res.benchmarks[0].id);
          // Pre-populate with typical OCR output
          setTestText(
            "श्रीगुरु चरन सरोज रज नजि मनु मुकुट सुधारा।\n" +
            "बरनउँ रघुबर बमिल जसु जो दायकु फल चारी॥\n" +
            "बुद्धिहीन तनु जानिके सुमिरौ पवन-कुमार।\n" +
            "बल बुधि बिद्या देहु मोहि हरहु कलेस बिकार॥"
          );
        }
      });
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const activeCase = cases.find((c) => c.id === selectedCaseId);

  const handleEvaluate = async () => {
    if (!activeCase || !testText) return;
    try {
      setIsEvaluating(true);
      const res = await api.evaluateBenchmark(activeCase.id, testText);
      setEvalResult(res.evaluation);
    } catch (e) {
      console.error(e);
    } finally {
      setIsEvaluating(false);
    }
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/60 backdrop-blur-xs p-3 sm:p-4 animate-in fade-in duration-150"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="benchmark-modal-title"
    >
      <div 
        className="bg-white rounded-2xl sm:rounded-3xl max-w-3xl w-full p-4 sm:p-7 shadow-2xl border border-stone-200 max-h-[92vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-3 sm:pb-4 border-b border-stone-100">
          <div className="flex items-center gap-2 sm:gap-2.5">
            <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-vedic-100 text-vedic-700 flex items-center justify-center shrink-0">
              <BarChart3 className="w-5 h-5" />
            </div>
            <div>
              <h2 id="benchmark-modal-title" className="text-base sm:text-lg font-bold text-stone-900 font-devanagari">
                {t.benchmarkTitle}
              </h2>
              <p className="text-[11px] sm:text-xs text-stone-500 font-devanagari">
                {t.benchmarkDesc}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 sm:p-2 rounded-xl text-stone-400 hover:text-stone-700 hover:bg-stone-100 transition-colors"
            aria-label={t.close}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Case Selector Tabs */}
        <div 
          role="tablist"
          aria-label="Benchmark cases"
          className="mt-3.5 sm:mt-5 flex gap-1.5 sm:gap-2 overflow-x-auto pb-1 text-xs no-scrollbar"
        >
          {cases.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => {
                setSelectedCaseId(c.id);
                setEvalResult(null);
              }}
              className={`px-3 py-1.5 rounded-xl font-medium transition-all whitespace-nowrap font-devanagari ${
                c.id === selectedCaseId
                  ? 'bg-vedic-700 text-white font-semibold shadow-2xs'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
              }`}
              aria-pressed={c.id === selectedCaseId}
            >
              {c.title.split('—')[0]}
            </button>
          ))}
        </div>

        {activeCase && (
          <div className="mt-3.5 space-y-3.5">
            {/* Case Details Badge */}
            <div className="p-3 sm:p-3.5 rounded-2xl bg-vedic-50/70 border border-vedic-200 text-xs flex flex-wrap items-center justify-between gap-2 font-devanagari">
              <div>
                <span className="font-bold text-vedic-950 block text-xs sm:text-sm">
                  {activeCase.title}
                </span>
                <span className="text-vedic-800 text-[11px]">
                  श्रेणी: {activeCase.genre} | कठिनाई: {activeCase.difficulty}
                </span>
              </div>
              <span className="text-[11px] text-vedic-950 bg-white px-2.5 py-1 rounded-lg border border-vedic-200 shadow-2xs">
                {activeCase.notes}
              </span>
            </div>

            {/* Split Comparison: Ground Truth vs Candidate Text */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">
              <div>
                <label className="block text-xs font-bold text-stone-700 mb-1 font-devanagari">
                  प्रामाणिक संदर्भ पाठ (Ground Truth):
                </label>
                <div className="p-3 sm:p-3.5 rounded-xl bg-emerald-50/50 border border-emerald-300 font-devanagari text-sm leading-[2] text-emerald-950 whitespace-pre-wrap min-h-[120px] shadow-2xs">
                  {activeCase.ground_truth}
                </div>
              </div>

              <div>
                <label htmlFor="benchmark-candidate-text" className="block text-xs font-bold text-stone-700 mb-1 font-devanagari">
                  परीक्षण हेतु OCR पाठ (Candidate Output):
                </label>
                <textarea
                  id="benchmark-candidate-text"
                  value={testText}
                  onChange={(e) => setTestText(e.target.value)}
                  className="w-full p-3 rounded-xl border border-stone-300 focus:outline-none focus:ring-2 focus:ring-vedic-500 font-devanagari text-sm leading-[2] min-h-[120px] resize-none shadow-2xs"
                  placeholder="यहाँ OCR का निकाला हुआ पाठ दर्ज करें..."
                />
              </div>
            </div>

            <div className="flex justify-end">
              <button
                type="button"
                onClick={handleEvaluate}
                disabled={isEvaluating || !testText.trim()}
                className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-vedic-700 hover:bg-vedic-800 disabled:opacity-40 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-2xs transition-colors font-devanagari"
              >
                {isEvaluating ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>परीक्षण हो रहा है...</span>
                  </>
                ) : (
                  <>
                    <span>{t.runTestBtn}</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </>
                )}
              </button>
            </div>

            {/* Evaluation Scorecard */}
            {evalResult && (
              <div className="mt-3.5 p-4 sm:p-5 rounded-2xl bg-stone-50 border border-stone-200 animate-in fade-in duration-150">
                {evalResult.status === 'Benchmark dataset not configured' ? (
                  <div className="p-4 rounded-xl bg-amber-50 border border-amber-300 text-amber-950 text-center font-devanagari text-xs">
                    <span className="font-bold block text-sm mb-1">मानक संदर्भ डेटासेट कॉन्फ़िगर नहीं है</span>
                    <span>(Benchmark dataset not configured) — कोई कृत्रिम या मिथ्या सटीकता अंक प्रदर्शित नहीं किए जाएँगे।</span>
                  </div>
                ) : (
                  <>
                    <h4 className="text-xs font-bold text-stone-500 uppercase tracking-wider mb-2.5 font-devanagari">
                      सटीकता मूल्यांकन परिणाम (Evaluation Scorecard)
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-center font-devanagari">
                      <div className="p-3 rounded-xl bg-white border border-stone-200 shadow-2xs">
                        <span className="text-xs text-stone-500 block">
                          {t.cerLabel}
                        </span>
                        <span className="text-2xl font-black text-stone-900 block mt-1">
                          {evalResult.cer_percentage}%
                        </span>
                        <span className="text-[10px] text-stone-400">
                          (निम्नतर बेहतर)
                        </span>
                      </div>

                      <div className="p-3 rounded-xl bg-white border border-stone-200 shadow-2xs">
                        <span className="text-xs text-stone-500 block">
                          {t.werLabel}
                        </span>
                        <span className="text-2xl font-black text-stone-800 block mt-1">
                          {evalResult.wer_percentage}%
                        </span>
                        <span className="text-[10px] text-stone-400">
                          (निम्नतर बेहतर)
                        </span>
                      </div>

                      <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-300 shadow-2xs">
                        <span className="text-xs text-emerald-900 block">
                          {t.accuracyLabel}
                        </span>
                        <span className="text-2xl font-black text-emerald-950 block mt-1">
                          {evalResult.accuracy_score_pct}%
                        </span>
                        <span className="text-[10px] text-emerald-700">
                          (100% - CER)
                        </span>
                      </div>
                    </div>

                    {/* Granular Sub-Error Rates */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-2.5 text-center font-devanagari text-xs">
                      <div className="p-2 rounded-lg bg-amber-50 border border-amber-200">
                        <span className="text-[10px] text-amber-800 block">मात्रा त्रुटि दर (Matra Error)</span>
                        <span className="font-bold text-amber-950 text-sm">{evalResult.matra_error_rate_pct ?? 'N/A'}%</span>
                      </div>
                      <div className="p-2 rounded-lg bg-stone-100 border border-stone-200">
                        <span className="text-[10px] text-stone-700 block">संयुक्ताक्षर त्रुटि (Conjunct)</span>
                        <span className="font-bold text-stone-900 text-sm">{evalResult.conjunct_error_rate_pct ?? 'N/A'}%</span>
                      </div>
                      <div className="p-2 rounded-lg bg-stone-100 border border-stone-200">
                        <span className="text-[10px] text-stone-600 block">विराम चिह्न त्रुटि (Punctuation)</span>
                        <span className="font-bold text-stone-900 text-sm">{evalResult.punctuation_error_rate_pct ?? 'N/A'}%</span>
                      </div>
                    </div>

                    <div className="mt-2.5 text-[11px] text-stone-500 text-center font-devanagari">
                      कुल संदर्भ वर्ण: {evalResult.reference_char_count} | निकाले गए वर्ण: {evalResult.extracted_char_count}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
