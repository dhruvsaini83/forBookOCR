import React, { useState, useEffect } from 'react';
import { X, BarChart3, ArrowRight } from 'lucide-react';
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div 
        className="bg-white rounded-3xl max-w-3xl w-full p-6 sm:p-8 shadow-2xl border border-stone-200 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-stone-100">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-xl bg-indigo-100 text-indigo-700 flex items-center justify-center">
              <BarChart3 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-stone-900 font-devanagari">
                {t.benchmarkTitle}
              </h2>
              <p className="text-xs text-stone-500 font-devanagari">
                {t.benchmarkDesc}
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

        {/* Case Selector Tabs */}
        <div className="mt-5 flex gap-2 overflow-x-auto pb-1 text-xs">
          {cases.map((c) => (
            <button
              key={c.id}
              onClick={() => {
                setSelectedCaseId(c.id);
                setEvalResult(null);
              }}
              className={`px-3.5 py-2 rounded-xl font-medium transition-all whitespace-nowrap font-devanagari ${
                c.id === selectedCaseId
                  ? 'bg-indigo-600 text-white font-semibold shadow-xs'
                  : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
              }`}
            >
              {c.title.split('—')[0]}
            </button>
          ))}
        </div>

        {activeCase && (
          <div className="mt-4 space-y-4">
            {/* Case Details Badge */}
            <div className="p-3.5 rounded-2xl bg-indigo-50/60 border border-indigo-200 text-xs flex flex-wrap items-center justify-between gap-2 font-devanagari">
              <div>
                <span className="font-bold text-indigo-950 block text-sm">
                  {activeCase.title}
                </span>
                <span className="text-indigo-800 text-[11px]">
                  श्रेणी: {activeCase.genre} | कठिनाई: {activeCase.difficulty}
                </span>
              </div>
              <span className="text-[11px] text-indigo-900 bg-white px-2.5 py-1 rounded-lg border border-indigo-200">
                {activeCase.notes}
              </span>
            </div>

            {/* Split Comparison: Ground Truth vs Candidate Text */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-stone-700 mb-1.5 font-devanagari">
                  प्रामाणिक संदर्भ पाठ (Ground Truth Transcription):
                </label>
                <div className="p-3.5 rounded-xl bg-emerald-50/40 border border-emerald-300 font-devanagari text-sm leading-relaxed text-emerald-950 whitespace-pre-wrap min-h-[140px]">
                  {activeCase.ground_truth}
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-stone-700 mb-1.5 font-devanagari">
                  परीक्षण हेतु OCR पाठ (Candidate Output):
                </label>
                <textarea
                  value={testText}
                  onChange={(e) => setTestText(e.target.value)}
                  className="w-full p-3 rounded-xl border border-stone-300 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-devanagari text-sm leading-relaxed min-h-[140px] resize-none"
                  placeholder="यहाँ OCR का निकाला हुआ पाठ दर्ज करें..."
                />
              </div>
            </div>

            <div className="flex justify-end">
              <button
                onClick={handleEvaluate}
                disabled={isEvaluating || !testText.trim()}
                className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-bold text-xs flex items-center gap-2 shadow-xs transition-colors font-devanagari"
              >
                <span>{isEvaluating ? 'परीक्षण हो रहा है...' : t.runTestBtn}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Evaluation Scorecard */}
            {evalResult && (
              <div className="mt-4 p-5 rounded-2xl bg-stone-50 border border-stone-200 animate-in fade-in duration-150">
                <h4 className="text-xs font-bold text-stone-500 uppercase tracking-wider mb-3 font-devanagari">
                  सटीकता मूल्यांकन परिणाम (Evaluation Scorecard)
                </h4>
                <div className="grid grid-cols-3 gap-3 text-center font-devanagari">
                  <div className="p-3 rounded-xl bg-white border border-stone-200 shadow-2xs">
                    <span className="text-xs text-stone-500 block">
                      {t.cerLabel}
                    </span>
                    <span className="text-2xl font-black text-indigo-900 block mt-1">
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
                    <span className="text-2xl font-black text-purple-900 block mt-1">
                      {evalResult.wer_percentage}%
                    </span>
                    <span className="text-[10px] text-stone-400">
                      (निम्नतर बेहतर)
                    </span>
                  </div>

                  <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-300 shadow-2xs">
                    <span className="text-xs text-emerald-800 block">
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

                <div className="mt-3 text-[11px] text-stone-500 text-center font-devanagari">
                  कुल संदर्भ वर्ण: {evalResult.reference_char_count} | निकाले गए वर्ण: {evalResult.extracted_char_count}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
