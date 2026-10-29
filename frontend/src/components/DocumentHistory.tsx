import React, { useState, useEffect, useCallback } from 'react';
import { X, Search, BookOpen, Trash2, Calendar, FileText, CheckCircle2, Clock } from 'lucide-react';
import type { DocumentData } from '../types';
import type { Language } from '../i18n/translations';
import { translations } from '../i18n/translations';
import { api } from '../services/api';

interface DocumentHistoryProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectDocument: (docId: string) => void;
  currentDocId?: string;
  lang: Language;
}

export const DocumentHistory: React.FC<DocumentHistoryProps> = ({
  isOpen,
  onClose,
  onSelectDocument,
  currentDocId,
  lang,
}) => {
  const t = translations[lang];
  const [documents, setDocuments] = useState<DocumentData[]>([]);
  const [search, setSearch] = useState<string>('');
  const [collection, setCollection] = useState<string>('सभी (All)');
  const [isLoading, setIsLoading] = useState<boolean>(false);

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

  const fetchDocs = useCallback(async () => {
    try {
      setIsLoading(true);
      const res = await api.listDocuments(search, collection);
      setDocuments(res.documents);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  }, [search, collection]);

  useEffect(() => {
    if (isOpen) {
      fetchDocs();
    }
  }, [isOpen, fetchDocs]);

  if (!isOpen) return null;

  const handleDelete = async (e: React.MouseEvent, docId: string) => {
    e.stopPropagation();
    if (window.confirm('क्या आप इस दस्तावेज़ को स्थायी रूप से हटाना चाहते हैं?')) {
      await api.deleteDocument(docId);
      fetchDocs();
    }
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-end bg-stone-900/50 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="history-drawer-title"
    >
      <div 
        className="bg-white h-full max-w-full sm:max-w-xl w-full p-4 sm:p-6 shadow-2xl flex flex-col border-l border-stone-200 animate-in slide-in-from-right duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-3 sm:pb-4 border-b border-stone-200">
          <div className="flex items-center gap-2.5">
            <BookOpen className="w-5 h-5 text-vedic-700" />
            <h2 id="history-drawer-title" className="text-base sm:text-lg font-bold text-stone-900 font-devanagari">
              {t.navHistory}
            </h2>
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

        {/* Search & Filters */}
        <div className="py-3 sm:py-4 space-y-2.5 sm:space-y-3">
          <div className="relative">
            <Search className="w-4 h-4 text-stone-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="शीर्षक अथवा देवनागरी पाठ में खोजें..."
              className="w-full pl-10 pr-4 py-2 sm:py-2.5 rounded-xl border border-stone-300 focus:outline-none focus:ring-2 focus:ring-vedic-500 text-sm font-devanagari"
              aria-label="Search documents"
            />
          </div>

          <div 
            role="tablist"
            aria-label="Filter collections"
            className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs no-scrollbar"
          >
            {['सभी (All)', 'सामान्य (General)', 'रामायण / रामकाव्य', 'भजन एवं पद संग्रह', 'संत साहित्य (कबीर/सूर/तुलसी)'].map((col) => (
              <button
                key={col}
                type="button"
                onClick={() => setCollection(col)}
                className={`px-3 py-1.5 rounded-lg whitespace-nowrap font-medium transition-colors font-devanagari ${
                  collection === col
                    ? 'bg-vedic-700 text-white font-semibold shadow-2xs'
                    : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
                }`}
                aria-pressed={collection === col}
              >
                {col}
              </button>
            ))}
          </div>
        </div>

        {/* Document List */}
        <div className="flex-1 overflow-y-auto space-y-2.5 sm:space-y-3 pr-1">
          {isLoading ? (
            <div className="p-8 text-center text-stone-400 text-sm font-devanagari">
              पुस्तकालय लोड हो रहा है...
            </div>
          ) : documents.length === 0 ? (
            <div className="p-8 text-center text-stone-400 text-sm font-devanagari">
              कोई दस्तावेज़ नहीं मिला।
            </div>
          ) : (
            documents.map((doc) => {
              const isSelected = doc.id === currentDocId;
              const isConfirmed = doc.verification_status === 'Manually Confirmed';
              const isVerified = doc.verification_status === 'Verified by Available Checks';

              return (
                <div
                  key={doc.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    onSelectDocument(doc.id);
                    onClose();
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelectDocument(doc.id);
                      onClose();
                    }
                  }}
                  className={`p-3.5 sm:p-4 rounded-2xl border cursor-pointer transition-all ${
                    isSelected
                      ? 'border-vedic-600 bg-vedic-50/70 shadow-2xs ring-1 ring-vedic-600'
                      : 'border-stone-200 bg-white hover:border-vedic-300 hover:bg-stone-50/70'
                  }`}
                  aria-label={`${doc.title}, ${doc.total_pages} pages`}
                >
                  <div className="flex items-start justify-between gap-2.5">
                    <div className="flex-1 min-w-0">
                      <h4 className="font-bold text-sm text-stone-900 truncate font-devanagari">
                        {doc.title}
                      </h4>
                      <p className="text-[11px] text-stone-500 truncate mt-0.5">
                        {doc.original_filename}
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={(e) => handleDelete(e, doc.id)}
                      className="p-1.5 rounded-lg text-stone-400 hover:text-rose-600 hover:bg-rose-50 transition-colors shrink-0"
                      title="हटाएँ"
                      aria-label="दस्तावेज़ हटाएँ"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Preview Text */}
                  {doc.preview_text && (
                    <p className="mt-2 text-xs text-stone-700 font-devanagari line-clamp-2 bg-stone-50 p-2 rounded-lg border border-stone-100">
                      {doc.preview_text}
                    </p>
                  )}

                  {/* Metadata & Status Footer */}
                  <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 text-[11px] text-stone-500 pt-2 border-t border-stone-100">
                    <div className="flex items-center gap-3">
                      <span className="flex items-center gap-1 font-devanagari">
                        <FileText className="w-3.5 h-3.5 text-stone-400" />
                        {doc.total_pages} पृष्ठ
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="w-3.5 h-3.5 text-stone-400" />
                        {new Date(doc.created_at).toLocaleDateString()}
                      </span>
                    </div>

                    <div>
                      {isConfirmed ? (
                        <span className="inline-flex items-center gap-1 text-blue-700 font-medium font-devanagari">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          प्रमाणित
                        </span>
                      ) : isVerified ? (
                        <span className="inline-flex items-center gap-1 text-emerald-700 font-medium font-devanagari">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          सत्यापित
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-amber-700 font-medium font-devanagari">
                          <Clock className="w-3.5 h-3.5" />
                          समीक्षा अपेक्षित
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};
