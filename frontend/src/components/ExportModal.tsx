import React, { useState, useEffect } from 'react';
import { X, FileText, Download, Code, Printer, AlertTriangle, CheckCircle } from 'lucide-react';
import type { Language } from '../i18n/translations';
import { translations } from '../i18n/translations';
import { api } from '../services/api';

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  docId: string;
  docTitle: string;
  unresolvedCount?: number;
  failedPagesCount?: number;
  lang: Language;
}

export const ExportModal: React.FC<ExportModalProps> = ({
  isOpen,
  onClose,
  docId,
  docTitle,
  unresolvedCount = 0,
  failedPagesCount = 0,
  lang,
}) => {
  const t = translations[lang];
  const [textVersion, setTextVersion] = useState<'reviewed' | 'original_ocr' | 'confirmed'>('reviewed');

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

  if (!isOpen) return null;

  const exportOptions = [
    {
      format: 'txt' as const,
      title: t.exportTxt,
      desc: 'सभी आधुनिक उपकरणों में सुगम पढ़ने योग्य स्वच्छ देवनागरी पाठ संचिका (UTF-8)',
      icon: <FileText className="w-5 h-5 text-emerald-600" />,
      color: 'hover:border-emerald-500 hover:bg-emerald-50/40',
    },
    {
      format: 'docx' as const,
      title: t.exportDocx,
      desc: 'Nirmala UI / Mangal देवनागरी फॉन्ट स्टैक सहित वर्ड संचिका (छंद संरेखण)',
      icon: <FileText className="w-5 h-5 text-blue-600" />,
      color: 'hover:border-blue-500 hover:bg-blue-50/40',
    },
    {
      format: 'json' as const,
      title: t.exportJson,
      desc: 'शोधार्थियों हेतु प्रत्येक शब्द के निर्देशांक, विश्वास स्तर, सिद्धान्त एवं ऑडिट ट्रेल',
      icon: <Code className="w-5 h-5 text-purple-600" />,
      color: 'hover:border-purple-500 hover:bg-purple-50/40',
    },
    {
      format: 'html' as const,
      title: t.exportHtml,
      desc: 'ब्राउज़र में सीधे देखने अथवा PDF के रूप में मुद्रित करने हेतु सुंदर वेब पृष्ठ',
      icon: <Printer className="w-5 h-5 text-amber-600" />,
      color: 'hover:border-amber-500 hover:bg-amber-50/40',
    },
  ];

  const handleDownload = (format: 'txt' | 'docx' | 'json' | 'html') => {
    const url = api.getExportUrl(docId, format, textVersion);
    window.open(url, '_blank');
  };

  const hasWarnings = unresolvedCount > 0 || failedPagesCount > 0;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/60 backdrop-blur-xs p-3 sm:p-4 animate-in fade-in duration-150"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="export-modal-title"
    >
      <div 
        className="bg-white rounded-2xl sm:rounded-3xl max-w-lg w-full p-4 sm:p-6 shadow-2xl border border-stone-200 max-h-[92vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-3 sm:pb-4 border-b border-stone-100">
          <div className="min-w-0 pr-2">
            <h3 id="export-modal-title" className="text-base sm:text-lg font-bold text-stone-900 font-devanagari">
              {t.exportModalTitle}
            </h3>
            <p className="text-xs text-stone-500 font-devanagari mt-0.5 truncate">
              {docTitle}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 sm:p-2 rounded-xl text-stone-400 hover:text-stone-700 hover:bg-stone-100 transition-colors shrink-0"
            aria-label={t.close}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Text Version Selection */}
        <div className="mt-3.5 p-3 bg-stone-50 rounded-xl sm:rounded-2xl border border-stone-200">
          <label className="block text-xs font-bold text-stone-700 mb-2 font-devanagari">
            निर्यात हेतु पाठ का प्रकार चुनें (Text Source):
          </label>
          <div 
            role="group"
            aria-label="Export text version"
            className="grid grid-cols-3 gap-1.5 sm:gap-2 text-xs font-devanagari"
          >
            <button
              type="button"
              onClick={() => setTextVersion('reviewed')}
              className={`p-2 rounded-xl border text-center transition-all ${
                textVersion === 'reviewed'
                  ? 'bg-vedic-700 text-white font-bold border-vedic-700 shadow-2xs'
                  : 'bg-white text-stone-700 border-stone-200 hover:bg-stone-100'
              }`}
              aria-pressed={textVersion === 'reviewed'}
            >
              समीक्षित पाठ
            </button>
            <button
              type="button"
              onClick={() => setTextVersion('original_ocr')}
              className={`p-2 rounded-xl border text-center transition-all ${
                textVersion === 'original_ocr'
                  ? 'bg-vedic-700 text-white font-bold border-vedic-700 shadow-2xs'
                  : 'bg-white text-stone-700 border-stone-200 hover:bg-stone-100'
              }`}
              aria-pressed={textVersion === 'original_ocr'}
            >
              मूल OCR
            </button>
            <button
              type="button"
              onClick={() => setTextVersion('confirmed')}
              className={`p-2 rounded-xl border text-center transition-all ${
                textVersion === 'confirmed'
                  ? 'bg-vedic-700 text-white font-bold border-vedic-700 shadow-2xs'
                  : 'bg-white text-stone-700 border-stone-200 hover:bg-stone-100'
              }`}
              aria-pressed={textVersion === 'confirmed'}
            >
              पुष्ट पाठ
            </button>
          </div>
        </div>

        {/* Warning Banner if Unresolved Flags or Failed Pages Exist */}
        {hasWarnings ? (
          <div className="mt-3 p-3 rounded-xl bg-amber-50 border border-amber-200 flex items-start gap-2 text-xs text-amber-950 font-devanagari">
            <AlertTriangle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
            <div>
              <span className="font-bold">समीक्षा सूचना: </span>
              {unresolvedCount > 0 && <span>इस दस्तावेज़ में {unresolvedCount} संदेहास्पद शब्द हैं। </span>}
              {failedPagesCount > 0 && <span>{failedPagesCount} पृष्ठ विफल हुए हैं। </span>}
              <span className="text-amber-800">निर्यात से पूर्व दृष्टिगत मिलान की अनुशंसा की जाती है।</span>
            </div>
          </div>
        ) : (
          <div className="mt-3 p-2.5 rounded-xl bg-emerald-50 border border-emerald-200 flex items-center gap-2 text-xs text-emerald-950 font-devanagari">
            <CheckCircle className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>दस्तावेज़ पूर्णतः विश्लेषित है।</span>
          </div>
        )}

        {/* Export Formats List */}
        <div className="mt-3.5 space-y-2">
          {exportOptions.map((opt) => (
            <div
              key={opt.format}
              className={`p-3 sm:p-3.5 rounded-2xl border border-stone-200 bg-white transition-all flex items-center justify-between gap-3 ${opt.color}`}
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="p-2 rounded-xl bg-stone-50 border border-stone-100 shrink-0">
                  {opt.icon}
                </div>
                <div className="min-w-0">
                  <h4 className="font-bold text-xs sm:text-sm text-stone-900 font-devanagari truncate">
                    {opt.title}
                  </h4>
                  <p className="text-[11px] text-stone-500 font-devanagari line-clamp-1">
                    {opt.desc}
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => handleDownload(opt.format)}
                className="px-3.5 py-2 rounded-xl bg-stone-100 hover:bg-vedic-700 hover:text-white text-stone-800 text-xs font-bold flex items-center gap-1.5 transition-colors shrink-0 font-devanagari shadow-2xs"
                aria-label={`Download ${opt.title}`}
              >
                <Download className="w-3.5 h-3.5" />
                <span>{t.downloadBtn}</span>
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
