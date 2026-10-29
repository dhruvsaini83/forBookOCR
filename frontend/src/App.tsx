import React, { useState, useEffect } from 'react';
import { 
  ChevronLeft, ChevronRight, Download, BookOpen, 
  RefreshCw, UploadCloud, LayoutGrid, FileText, Image as ImageIcon, Crop
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
import { ImageAdjustmentModal } from './components/ImageAdjustmentModal';
import { ComparisonModal } from './components/ComparisonModal';
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
  const [unresolvedInfo, setUnresolvedInfo] = useState<{
    total_unresolved_pages: number;
    total_flagged_tokens: number;
    failed_pages_count: number;
    pages: any[];
  } | null>(null);

  // Responsive Workspace Mode ('split' | 'image' | 'text')
  const [workspaceMode, setWorkspaceMode] = useState<'split' | 'image' | 'text'>('split');

  // Modals
  const [isUploadOpen, setIsUploadOpen] = useState<boolean>(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState<boolean>(false);
  const [isBenchmarkOpen, setIsBenchmarkOpen] = useState<boolean>(false);
  const [isExportOpen, setIsExportOpen] = useState<boolean>(false);
  const [isAdjustmentOpen, setIsAdjustmentOpen] = useState<boolean>(false);
  const [isComparisonOpen, setIsComparisonOpen] = useState<boolean>(false);

  const handleApplyAdjustmentSuccess = async (pageNum: number) => {
    if (!currentDoc) return;
    await loadDocument(currentDoc.id, pageNum);
  };

  const handleResetAdjustment = async () => {
    if (!currentDoc || !currentPage) return;
    try {
      setIsLoading(true);
      await api.resetAdjustment(currentDoc.id, currentPageNum, true);
      await loadDocument(currentDoc.id, currentPageNum);
    } catch (err) {
      console.error('Failed to reset adjustment', err);
    } finally {
      setIsLoading(false);
    }
  };

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

      // Fetch unresolved pages & flagged tokens summary
      try {
        const unres = await api.getDocumentUnresolved(docId);
        setUnresolvedInfo(unres);
      } catch (e) {
        console.error('Failed to fetch unresolved summary', e);
      }
    } catch (err) {
      console.error('Failed to load document', err);
    } finally {
      setIsLoading(false);
    }
  };

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

  const handleRetryPage = async (pageNum: number) => {
    if (!currentDoc) return;
    try {
      setIsLoading(true);
      await api.retryPage(currentDoc.id, pageNum);
      const p = await api.getPage(currentDoc.id, pageNum);
      setCurrentPage(p);
      const unres = await api.getDocumentUnresolved(currentDoc.id);
      setUnresolvedInfo(unres);
    } catch (err) {
      console.error('Failed to retry page', err);
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
    <div className="min-h-screen flex flex-col bg-[#faf8f5] text-stone-900 font-sans antialiased selection:bg-vedic-200 selection:text-vedic-950">
      {/* Header */}
      <Header
        lang={lang}
        onToggleLang={() => setLang(lang === 'hi' ? 'en' : 'hi')}
        onChangeLang={(newLang) => setLang(newLang)}
        onOpenUpload={() => setIsUploadOpen(true)}
        onOpenHistory={() => setIsHistoryOpen(true)}
        onOpenBenchmark={() => setIsBenchmarkOpen(true)}
        onOpenSamples={() => setIsUploadOpen(true)}
        activeDocTitle={currentDoc?.title}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 flex flex-col gap-4 sm:gap-6">
        {/* Document Subheader & Page Navigation */}
        {currentDoc && (
          <div className="flex flex-wrap items-center justify-between gap-3 sm:gap-4 p-3.5 sm:p-4 rounded-2xl bg-white border border-stone-200/90 shadow-2xs">
            <div className="flex items-center gap-2.5 sm:gap-3 min-w-0 flex-1">
              <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-vedic-100 text-vedic-800 flex items-center justify-center shrink-0">
                <BookOpen className="w-5 h-5 text-vedic-700" />
              </div>
              <div className="min-w-0">
                <h2 className="text-sm sm:text-base font-bold text-stone-900 font-devanagari truncate">
                  {currentDoc.title}
                </h2>
                <span className="text-[11px] sm:text-xs text-stone-500 font-devanagari truncate block">
                  श्रेणी: {currentDoc.collection_name} | {currentDoc.original_filename}
                </span>
              </div>
            </div>

            {/* Page Navigator & Export Button */}
            <div className="flex items-center gap-2 sm:gap-3 shrink-0 flex-wrap">
              {currentDoc.total_pages > 1 && (
                <div 
                  role="navigation"
                  aria-label="Page navigation"
                  className="flex items-center gap-1.5 sm:gap-2 bg-stone-100 p-1 rounded-xl text-xs font-devanagari border border-stone-200/60"
                >
                  <button
                    type="button"
                    onClick={() => handlePageChange(currentPageNum - 1)}
                    disabled={currentPageNum <= 1 || isLoading}
                    className="p-1 sm:p-1.5 rounded-lg bg-white border border-stone-200 text-stone-700 disabled:opacity-40 hover:bg-stone-50 shadow-2xs"
                    title={t.prevPage}
                    aria-label={t.prevPage}
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="font-semibold text-stone-800 px-1 sm:px-2 text-xs">
                    {t.pageNavigator} {currentPageNum} {t.ofPages} {currentDoc.total_pages}
                  </span>
                  <button
                    type="button"
                    onClick={() => handlePageChange(currentPageNum + 1)}
                    disabled={currentPageNum >= currentDoc.total_pages || isLoading}
                    className="p-1 sm:p-1.5 rounded-lg bg-white border border-stone-200 text-stone-700 disabled:opacity-40 hover:bg-stone-50 shadow-2xs"
                    title={t.nextPage}
                    aria-label={t.nextPage}
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              )}

              {/* Crop & Rotate Adjustment Studio Button */}
              <button
                type="button"
                onClick={() => setIsAdjustmentOpen(true)}
                className="inline-flex items-center gap-1.5 sm:gap-2 px-3 sm:px-3.5 py-2 rounded-xl border border-vedic-200 bg-vedic-50 hover:bg-vedic-100 text-vedic-900 text-xs font-semibold shadow-2xs transition-colors font-devanagari"
                aria-label={t.adjustImageBtn}
              >
                <Crop className="w-4 h-4 text-vedic-700" />
                <span>{t.adjustImageBtn}</span>
              </button>

              {/* Export Button */}
              <button
                type="button"
                onClick={() => setIsExportOpen(true)}
                className="inline-flex items-center gap-1.5 sm:gap-2 px-3 sm:px-3.5 py-2 rounded-xl border border-stone-200 bg-white hover:bg-stone-50 text-stone-700 text-xs font-semibold shadow-2xs transition-colors font-devanagari"
                aria-label={t.downloadDoc}
              >
                <Download className="w-4 h-4 text-vedic-700" />
                <span>{t.downloadDoc}</span>
              </button>
            </div>
          </div>
        )}

        {/* Workspace Mode Switcher (Visible on mobile/tablet, and helpful on desktop) */}
        {currentPage && !isLoading && (
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <div 
              role="tablist"
              aria-label="Workspace view modes"
              className="inline-flex bg-stone-100 p-1 rounded-xl border border-stone-200 shadow-2xs text-xs font-devanagari"
            >
              <button
                type="button"
                onClick={() => setWorkspaceMode('image')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                  workspaceMode === 'image'
                    ? 'bg-white text-vedic-950 font-bold shadow-2xs'
                    : 'text-stone-600 hover:text-stone-900 font-medium'
                }`}
                aria-pressed={workspaceMode === 'image'}
              >
                <ImageIcon className="w-3.5 h-3.5 text-vedic-700" />
                <span>{t.workspaceModeScan}</span>
              </button>
              <button
                type="button"
                onClick={() => setWorkspaceMode('text')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                  workspaceMode === 'text'
                    ? 'bg-white text-vedic-950 font-bold shadow-2xs'
                    : 'text-stone-600 hover:text-stone-900 font-medium'
                }`}
                aria-pressed={workspaceMode === 'text'}
              >
                <FileText className="w-3.5 h-3.5 text-emerald-700" />
                <span>{t.workspaceModeEditor}</span>
              </button>
              <button
                type="button"
                onClick={() => setWorkspaceMode('split')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                  workspaceMode === 'split'
                    ? 'bg-white text-vedic-950 font-bold shadow-2xs'
                    : 'text-stone-600 hover:text-stone-900 font-medium'
                }`}
                aria-pressed={workspaceMode === 'split'}
              >
                <LayoutGrid className="w-3.5 h-3.5 text-indigo-700" />
                <span>{t.workspaceModeSplit}</span>
              </button>
            </div>

            <span className="text-[11px] text-stone-500 font-devanagari hidden sm:inline">
              ⚡ ५-चरणीय सत्यापन सक्रिय
            </span>
          </div>
        )}

        {/* Loading Spinner */}
        {isLoading && (
          <div className="p-8 sm:p-12 text-center text-vedic-800 font-devanagari flex flex-col items-center justify-center gap-3 bg-white rounded-3xl border border-stone-200/90 shadow-2xs my-4">
            <RefreshCw className="w-8 h-8 animate-spin text-vedic-700" />
            <span className="text-sm font-semibold">पाण्डुलिपि एवं देवनागरी पाठ का बहु-चरणीय विश्लेषण हो रहा है...</span>
          </div>
        )}

        {/* Responsive Workspace */}
        {currentPage && !isLoading && (
          <div className={`grid gap-4 sm:gap-6 items-start ${
            workspaceMode === 'split' 
              ? 'grid-cols-1 lg:grid-cols-2' 
              : 'grid-cols-1'
          }`}>
            {/* Left: Original Image & Bounding Boxes */}
            {(workspaceMode === 'split' || workspaceMode === 'image') && (
              <div className="h-[520px] sm:h-[600px] lg:h-[720px] w-full">
                <ImageViewer
                  originalUrl={currentPage.original_image_path}
                  enhancedUrl={currentPage.preprocessed_image_path}
                  adjustedUrl={currentPage.adjusted_image_path}
                  optimizedUrl={currentPage.optimized_image_path}
                  compressionMetadata={currentPage.compression_metadata}
                  tokens={currentPage.word_tokens}
                  selectedWordIndex={selectedWordIndex}
                  onSelectWord={handleWordSelect}
                  onOpenAdjustment={() => setIsAdjustmentOpen(true)}
                  onResetAdjustment={handleResetAdjustment}
                  onOpenComparison={() => setIsComparisonOpen(true)}
                  lang={lang}
                />
              </div>
            )}

            {/* Right: Verified Text Editor & Copy Bar */}
            {(workspaceMode === 'split' || workspaceMode === 'text') && (
              <div className="h-[520px] sm:h-[600px] lg:h-[720px] w-full">
                <TextEditor
                  verifiedText={currentPage.verified_text}
                  rawText={currentPage.raw_ocr_text}
                  confirmedText={currentPage.confirmed_text}
                  tokens={currentPage.word_tokens}
                  selectedWordIndex={selectedWordIndex}
                  onSelectWord={handleWordSelect}
                  onSaveFullText={handleSaveFullText}
                  verificationStatus={currentDoc?.verification_status || 'Needs Review'}
                  pageStatus={currentPage.status}
                  onRetryPage={() => handleRetryPage(currentPageNum)}
                  lang={lang}
                />
              </div>
            )}
          </div>
        )}

        {/* Empty State when no document */}
        {!currentDoc && !isLoading && (
          <div className="p-8 sm:p-12 text-center bg-white rounded-3xl border border-stone-200/90 shadow-2xs max-w-xl mx-auto my-8">
            <div className="w-16 h-16 rounded-2xl bg-vedic-100 text-vedic-700 flex items-center justify-center mx-auto mb-4 shadow-2xs">
              <UploadCloud className="w-8 h-8" />
            </div>
            <h3 className="text-lg font-bold text-stone-900 font-devanagari mb-1">
              {lang === 'hi' ? 'कोई दस्तावेज़ चयनित नहीं है' : 'No Document Selected'}
            </h3>
            <p className="text-xs sm:text-sm text-stone-500 font-devanagari mb-6">
              {lang === 'hi' 
                ? 'कृपया नई पाण्डुलिपि अपलोड करें अथवा पुस्तकालय से कोई ऐतिहासिक ग्रन्थ चुनें।'
                : 'Please upload a new manuscript scan or choose a historical sample to begin.'}
            </p>
            <button
              type="button"
              onClick={() => setIsUploadOpen(true)}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-vedic-700 hover:bg-vedic-800 text-white font-bold text-sm shadow-2xs font-devanagari transition-colors"
            >
              <UploadCloud className="w-4 h-4" />
              <span>{t.navUpload}</span>
            </button>
          </div>
        )}

        {/* 5-Stage Verification Summary Panel */}
        {currentPage && !isLoading && (
          <VerificationPanel
            metrics={currentPage.stage_metrics}
            unresolvedCount={unresolvedInfo?.total_flagged_tokens || 0}
            failedPagesCount={unresolvedInfo?.failed_pages_count || 0}
            lang={lang}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-stone-200 bg-white py-5 sm:py-6 text-center text-xs text-stone-500 font-devanagari">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2.5">
          <span>
            वाणीसंशोधक (VaniScript Heritage OCR) — प्राचीन धार्मिक ग्रन्थों एवं देवनागरी पाण्डुलिपियों का डिजिटल संरक्षण
          </span>
          <span className="font-mono text-stone-400 text-[11px]">
            वर्जन 2.1.0 | निष्पक्ष ५-चरणीय सत्यापन
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
        onUploadSuccess={async (docId, shouldAdjust) => {
          await loadDocument(docId, 1);
          if (shouldAdjust) {
            setIsAdjustmentOpen(true);
          }
        }}
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
          unresolvedCount={unresolvedInfo?.total_flagged_tokens || 0}
          failedPagesCount={unresolvedInfo?.failed_pages_count || 0}
          lang={lang}
        />
      )}

      {currentDoc && currentPage && (
        <ImageAdjustmentModal
          isOpen={isAdjustmentOpen}
          onClose={() => setIsAdjustmentOpen(false)}
          documentId={currentDoc.id}
          pageNumber={currentPageNum}
          totalPages={currentDoc.total_pages}
          originalImageUrl={currentPage.original_image_path}
          currentAdjustment={currentPage.adjustment_metadata}
          onApplySuccess={handleApplyAdjustmentSuccess}
          onSkip={async () => {
            setIsAdjustmentOpen(false);
            if (currentPage.status === 'PENDING_ADJUSTMENT' || !currentPage.raw_ocr_text) {
              setIsLoading(true);
              try {
                await api.processDocument(currentDoc.id, currentPageNum);
                await loadDocument(currentDoc.id, currentPageNum);
              } finally {
                setIsLoading(false);
              }
            }
          }}
          lang={lang}
        />
      )}

      {currentDoc && currentPage && (
        <ComparisonModal
          isOpen={isComparisonOpen}
          onClose={() => setIsComparisonOpen(false)}
          documentId={currentDoc.id}
          pageNumber={currentPageNum}
          originalImageUrl={currentPage.original_image_path}
          initialComparison={
            currentPage.comparison_data && 
            typeof currentPage.comparison_data === 'object' &&
            Object.keys(currentPage.comparison_data).length > 0 &&
            'summary' in currentPage.comparison_data
              ? currentPage.comparison_data 
              : null
          }
          lang={lang}
          onSelectEngineSuccess={async () => {
            await loadDocument(currentDoc.id, currentPageNum);
          }}
        />
      )}
    </div>
  );
};
