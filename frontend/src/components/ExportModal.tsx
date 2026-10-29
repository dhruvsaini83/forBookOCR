import React from 'react';
import { X, FileText, Download, Code, Printer } from 'lucide-react';
import type { Language } from '../i18n/translations';
import { translations } from '../i18n/translations';
import { api } from '../services/api';

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  docId: string;
  docTitle: string;
  lang: Language;
}

export const ExportModal: React.FC<ExportModalProps> = ({
  isOpen,
  onClose,
  docId,
  docTitle,
  lang,
}) => {
  const t = translations[lang];

  if (!isOpen) return null;

  const exportOptions = [
    {
      format: 'txt' as const,
      title: t.exportTxt,
      desc: 'सभी आधुनिक उपकरणों में सुगम पढ़ने योग्य स्वच्छ देवनागरी पाठ संचिका',
      icon: <FileText className="w-5 h-5 text-emerald-600" />,
      color: 'hover:border-emerald-500 hover:bg-emerald-50/40',
    },
    {
      format: 'docx' as const,
      title: t.exportDocx,
      desc: 'परंपरागत मुद्रण शैली, छंद केन्द्रीकरण एवं पृष्ठ क्रमांक सहित वर्ड संचिका',
      icon: <FileText className="w-5 h-5 text-blue-600" />,
      color: 'hover:border-blue-500 hover:bg-blue-50/40',
    },
    {
      format: 'json' as const,
      title: t.exportJson,
      desc: 'शोधार्थियों हेतु प्रत्येक शब्द के निर्देशांक, विश्वास स्तर एवं सत्यापन लेखा',
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
    const url = api.getExportUrl(docId, format);
    window.open(url, '_blank');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div 
        className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-stone-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-stone-100">
          <div>
            <h3 className="text-lg font-bold text-stone-900 font-devanagari">
              {t.exportModalTitle}
            </h3>
            <p className="text-xs text-stone-500 font-devanagari mt-0.5 truncate max-w-xs">
              {docTitle}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl text-stone-400 hover:text-stone-600 hover:bg-stone-100"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Export Options Grid */}
        <div className="mt-5 space-y-3">
          {exportOptions.map((opt) => (
            <div
              key={opt.format}
              onClick={() => handleDownload(opt.format)}
              className={`p-4 rounded-2xl border border-stone-200 bg-stone-50/60 cursor-pointer transition-all flex items-center justify-between gap-3 group ${opt.color}`}
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-white border border-stone-200 flex items-center justify-center shrink-0 shadow-2xs">
                  {opt.icon}
                </div>
                <div>
                  <h4 className="font-bold text-sm text-stone-900 font-devanagari">
                    {opt.title}
                  </h4>
                  <p className="text-xs text-stone-500 font-devanagari mt-0.5">
                    {opt.desc}
                  </p>
                </div>
              </div>
              <button
                type="button"
                className="p-2.5 rounded-xl bg-white border border-stone-200 text-stone-700 group-hover:bg-vedic-600 group-hover:text-white group-hover:border-vedic-600 shadow-2xs transition-all"
                title={t.downloadBtn}
              >
                <Download className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>

        <div className="mt-5 p-3 rounded-xl bg-stone-100 text-[11px] text-stone-600 text-center font-devanagari">
          सभी प्रारूपों में देवनागरी यूनिकोड (UTF-8) पूर्णतः संरक्षित रहता है।
        </div>
      </div>
    </div>
  );
};
