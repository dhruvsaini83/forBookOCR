import React, { useState, useEffect } from 'react';
import { 
  ChevronLeft, ChevronRight, Download, BookOpen, 
  RefreshCw 
} from 'lucide-react';
import { Header } from './components/Header';
import { ImageViewer } from './components/ImageViewer';
import { TextEditor } from './components/TextEditor';
import { VerificationPanel } from './components/VerificationPanel';
import { WordInspectorModal } from './components/WordInspectorModal';
import { UploadModal } from './components/UploadModal';
import { DocumentHistory } from './components/DocumentHistory';
import { BenchmarkModal } from './components/BenchmarkModal';
import { ExportModal } from './components/ExportModal';
import type { Language } from './i18n/translations';
import { translations } from './i18n/translations';
import type { DocumentData, PageData, WordToken } from './types';
import { api } from './services/api';

export const App: React.FC = () => {
  const [lang, setLang] = useState<Language>('hi');
  const t = translations[lang];

  // Document & Page State
  const [currentDoc, setCurrentDoc] = useState<DocumentData | null>(null);
  const [currentPage, setCurrentPage] = useState<PageData | null>(null);
  const [currentPageNum, setCurrentPageNum] = useState<number>(1);
  const [selectedWordIndex, setSelectedWordIndex] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [samples, setSamples] = useState<any[]>([]);

  // Modals
  const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(false);
  const [isBenchmarkOpen, setIsBenchmarkOpen] = useState<boolean>(false);
  const [isExportOpen, setIsExportOpen] = useState<boolean>(false);

  // Initial Load: Fetch samples and load the first historical document
  useEffect(() => {
    const initApp = async () => {
      try {
        setIsLoading(true);
        const sampleRes = await api.listSamples();
        setSamples(sampleRes.samples);

        // Check if existing documents exist in history
        const docRes = await api.listDocuments();
        if (docRes.documents.length > 0) {
          await loadDocument(docRes.documents[0].id);
        } else if (sampleRes.samples.length > 0) {
          // Auto-load first sample (Ramcharitmanas Chaupai)
          const loadRes = await api.loadSample(sampleRes.samples[0].id);
          await loadDocument(loadRes.document_id);
        }
      } catch (err) {
        console.error('Initialization error', err);
      } finally {
        setIsLoading(false);
      }
    };

    initApp();
  }, []);

  const loadDocument = async (docId: string, pageNum = 1) => {
    try {
      setIsLoading(true);
      const res = await api.getDocument(docId);
      setCurrentDoc(res.document);
      setCurrentPageNum(pageNum);

      if (res.pages && res.pages.length > 0) {
        const p = res.pages.find((pg) => pg.page_number === pageNum) || res.pages[0];
        setCurrentPage(p);
      } else {
        // Fetch specific page
        const p = await api.getPage(docId, pageNum);
        setCurrentPage(p);
      }
      setSelectedWordIndex(null);
    } catch (err) {
      console.error('Failed to load document', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePageChange = async (newPageNum: number) => {
    if (!currentDoc || newPageNum < 1 || newPageNum > currentDoc.total_pages) return;
    try {
      setIsLoading(true);
      setCurrentPageNum(newPageNum);
      const p = await api.getPage(currentDoc.id, newPageNum);
      setCurrentPage(p);
      setSelectedWordIndex(null);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleWordSelect = (index: number) => {
    setSelectedWordIndex(index);
  };

  const handleApplyWordCorrection = async (wordIndex: number, newText: string, reason = 'manual_correction') => {
    if (!currentDoc || !currentPage) return;
    try {
      const res = await api.updateWord(currentDoc.id, currentPageNum, wordIndex, newText, reason);
      if (res.success) {
        // Refresh current page
        const updatedPage = await api.getPage(currentDoc.id, currentPageNum);
        setCurrentPage(updatedPage);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleSaveFullText = async (newText: string, markConfirmed = false) => {
    if (!currentDoc || !currentPage) return;
    try {
      await api.updatePageText(currentDoc.id, currentPageNum, newText, markConfirmed);
      const updatedPage = await api.getPage(currentDoc.id, currentPageNum);
      setCurrentPage(updatedPage);
      if (markConfirmed) {
        const docRes = await api.getDocument(currentDoc.id);
        setCurrentDoc(docRes.document);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleLoadSampleFromModal = async (sampleId: string) => {
    try {
      setIsLoading(true);
      const res = await api.loadSample(sampleId);
      await loadDocument(res.document_id);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const selectedWordToken: WordToken | null = 
    currentPage && selectedWordIndex !== null && currentPage.word_tokens[selectedWordIndex]
      ? currentPage.word_tokens[selectedWordIndex]
      : null;

  return (
    <div className="min-h-screen flex flex-col bg-[#faf8f5] text-stone-900 font-sans">
      {/* Header */}
      <Header
        lang={lang}
        onToggleLang={() => setLang(lang === 'hi' ? 'en' : 'hi')}
        onOpenUpload={() => setIsUploadOpen(true)}
        onOpenHistory={() => setIsHistoryOpen(true)}
        onOpenBenchmark={() => setIsBenchmarkOpen(true)}
        onOpenSamples={() => setIsUploadOpen(true)}
        activeDocTitle={currentDoc?.title}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col gap-6">
        {/* Document Subheader & Page Navigation */}
        {currentDoc && (
          <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-2xl bg-white border border-stone-200/90 shadow-2xs">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-vedic-100 text-vedic-800 flex items-center justify-center shrink-0">
                <BookOpen className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-stone-900 font-devanagari">
                  {currentDoc.title}
                </h2>
                <span className="text-xs text-stone-500 font-devanagari">
                  श्रेणी: {currentDoc.collection_name} | {currentDoc.original_filename}
                </span>
              </div>
            </div>

            {/* Page Navigator */}
            <div className="flex items-center gap-3">
              {currentDoc.total_pages > 1 && (
                <div className="flex items-center gap-2 bg-stone-100 p-1 rounded-xl text-xs font-devanagari">
                  <button
                    onClick={() => handlePageChange(currentPageNum - 1)}
                    disabled={currentPageNum <= 1 || isLoading}
                    className="p-1.5 rounded-lg bg-white border border-stone-200 text-stone-700 disabled:opacity-40 hover:bg-stone-50"
                    title={t.prevPage}
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="font-semibold text-stone-800 px-2">
                    {t.pageNavigator} {currentPageNum} {t.ofPages} {currentDoc.total_pages}
                  </span>
                  <button
                    onClick={() => handlePageChange(currentPageNum + 1)}
                    disabled={currentPageNum >= currentDoc.total_pages || isLoading}
                    className="p-1.5 rounded-lg bg-white border border-stone-200 text-stone-700 disabled:opacity-40 hover:bg-stone-50"
                    title={t.nextPage}
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              )}

              {/* Export Button */}
              <button
                onClick={() => setIsExportOpen(true)}
                className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl border border-stone-200 bg-white hover:bg-stone-50 text-stone-700 text-xs font-semibold shadow-2xs transition-colors font-devanagari"
              >
                <Download className="w-4 h-4 text-vedic-700" />
                <span>{t.downloadDoc}</span>
              </button>
            </div>
          </div>
        )}

        {/* Loading Spinner */}
        {isLoading && (
          <div className="p-8 text-center text-vedic-700 font-devanagari flex items-center justify-center gap-2">
            <RefreshCw className="w-5 h-5 animate-spin" />
            <span>पाण्डुलिपि एवं देवनागरी पाठ का बहु-चरणीय विश्लेषण हो रहा है...</span>
          </div>
        )}

        {/* Split Screen Workspace */}
        {currentPage && !isLoading && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
            {/* Left: Original Image & Bounding Boxes */}
            <div className="h-[680px]">
              <ImageViewer
                originalUrl={currentPage.original_image_path}
                enhancedUrl={currentPage.preprocessed_image_path}
                tokens={currentPage.word_tokens}
                selectedWordIndex={selectedWordIndex}
                onSelectWord={handleWordSelect}
                lang={lang}
              />
            </div>

            {/* Right: Verified Text Editor & Copy Bar */}
            <div className="h-[680px]">
              <TextEditor
                verifiedText={currentPage.verified_text}
                rawText={currentPage.raw_ocr_text}
                tokens={currentPage.word_tokens}
                selectedWordIndex={selectedWordIndex}
                onSelectWord={handleWordSelect}
                onSaveFullText={handleSaveFullText}
                verificationStatus={currentDoc?.verification_status || 'Needs Review'}
                lang={lang}
              />
            </div>
          </div>
        )}

        {/* 4-Stage Verification Summary Panel */}
        {currentPage && !isLoading && (
          <VerificationPanel
            metrics={currentPage.stage_metrics}
            lang={lang}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-stone-200 bg-white py-6 text-center text-xs text-stone-500 font-devanagari">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <span>
            वाणीसंशोधक (VaniScript Heritage OCR) — प्राचीन धार्मिक ग्रन्थों एवं देवनागरी पाण्डुलिपियों का डिजिटल संरक्षण
          </span>
          <span className="font-mono text-stone-400">
            वर्जन 2.0.0 | पूर्णतः निष्पक्ष बहु-चरणीय सत्यापन
          </span>
        </div>
      </footer>

      {/* Modals */}
      <WordInspectorModal
        token={selectedWordToken}
        onClose={() => setSelectedWordIndex(null)}
        onApplyCorrection={handleApplyWordCorrection}
        lang={lang}
      />

      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={(docId) => loadDocument(docId)}
        onLoadSample={handleLoadSampleFromModal}
        samples={samples}
        lang={lang}
      />

      <DocumentHistory
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        onSelectDocument={(docId) => loadDocument(docId)}
        currentDocId={currentDoc?.id}
        lang={lang}
      />

      <BenchmarkModal
        isOpen={isBenchmarkOpen}
        onClose={() => setIsBenchmarkOpen(false)}
        lang={lang}
      />

      {currentDoc && (
        <ExportModal
          isOpen={isExportOpen}
          onClose={() => setIsExportOpen(false)}
          docId={currentDoc.id}
          docTitle={currentDoc.title}
          lang={lang}
        />
      )}
    </div>
  );
};
