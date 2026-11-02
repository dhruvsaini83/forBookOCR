import React, { useState, useEffect, useRef } from 'react';
import { 
  AlertTriangle, BookOpen, ChevronLeft, ChevronRight, 
  Sparkles, Search, Check, RefreshCw, ZoomIn, ZoomOut, 
  ArrowLeft, BrainCircuit, Lightbulb, Zap, X
} from 'lucide-react';
import { api, getStorageUrl } from '../services/api';
import type { BookData, PageData, WordToken, SuggestionItem } from '../types';
import type { Language } from '../i18n/translations';

interface VerifyProps {
  initialBookId?: string | null;
  initialDocId?: string | null;
  initialPageNumber?: number;
  lang: Language;
  onBackToBooks?: () => void;
  onNavigateToBuilder?: (bookId: string) => void;
  onOpenLearning?: (bookId?: string) => void;
}

interface ToastMessage {
  id: string;
  text: string;
  type: 'learning' | 'success' | 'error';
}

export const Verify: React.FC<VerifyProps> = ({
  initialBookId,
  initialPageNumber = 1,
  onBackToBooks,
  onNavigateToBuilder,
  onOpenLearning
}) => {
  // Books & Navigation State
  const [books, setBooks] = useState<BookData[]>([]);
  const [selectedBookId, setSelectedBookId] = useState<string | null>(initialBookId || null);
  const [pages, setPages] = useState<PageData[]>([]);
  const [currentPageIndex, setCurrentPageIndex] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<PageData | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Word Tokens & Local Edits
  const [tokens, setTokens] = useState<WordToken[]>([]);
  const [editedWords, setEditedWords] = useState<Record<number, string>>({});
  const [selectedWordIdx, setSelectedWordIdx] = useState<number | null>(null);
  const [filterMode, setFilterMode] = useState<'all' | 'flagged' | 'verified'>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Suggestion Engine State
  const [suggestionsMap, setSuggestionsMap] = useState<Record<number, SuggestionItem>>({});
  const [ignoredSuggestions, setIgnoredSuggestions] = useState<Record<number, boolean>>({});
  const [isFetchingSuggestions, setIsFetchingSuggestions] = useState<boolean>(false);
  // Setting: 'suggestion' (Manual Approval) vs 'auto' (Auto-Correct: freq > 5 & conf > 0.9)
  const [correctionMode, setCorrectionMode] = useState<'suggestion' | 'auto'>('suggestion');

  // Learning Toast State
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  // Statistics
  const [learnedCount, setLearnedCount] = useState<number>(0);
  const [learnedWordsList, setLearnedWordsList] = useState<any[]>([]);
  const [showLearnedModal, setShowLearnedModal] = useState<boolean>(false);

  // Image Zoom / Pan State
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const imageContainerRef = useRef<HTMLDivElement>(null);

  const showToast = (text: string, type: 'learning' | 'success' | 'error' = 'learning') => {
    const id = `${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    setToasts((prev) => [...prev, { id, text, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((toast) => toast.id !== id));
    }, 4000);
  };

  // 1. Fetch available books on mount
  useEffect(() => {
    const fetchBooks = async () => {
      try {
        const res = await api.listBooks();
        if (res && res.books) {
          setBooks(res.books);
          if (!selectedBookId && res.books.length > 0) {
            setSelectedBookId(res.books[0].id);
          }
        }
      } catch (err) {
        console.error('Failed to load books in Verify page', err);
      }
    };
    fetchBooks();
  }, [selectedBookId]);

  // 2. Fetch pages when selected book changes
  useEffect(() => {
    if (!selectedBookId) return;

    const fetchBookDetails = async () => {
      setIsLoading(true);
      try {
        const pagesRes = await api.getBookPages(selectedBookId);
        if (pagesRes && pagesRes.pages && pagesRes.pages.length > 0) {
          setPages(pagesRes.pages);
          const targetIndex = initialPageNumber 
            ? Math.max(0, Math.min(pagesRes.pages.length - 1, initialPageNumber - 1))
            : 0;
          setCurrentPageIndex(targetIndex);
          loadPageData(pagesRes.pages[targetIndex]);
        } else {
          setPages([]);
          setCurrentPage(null);
          setTokens([]);
        }

        // Fetch learned words count
        const learnedRes = await api.getLearnedWords(selectedBookId, 50);
        if (learnedRes && learnedRes.words) {
          setLearnedWordsList(learnedRes.words);
          setLearnedCount(learnedRes.total || learnedRes.words.length);
        }
      } catch (err) {
        console.error('Failed to fetch book pages for verification', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchBookDetails();
  }, [selectedBookId, initialPageNumber]);

  // 3. Auto-Correct Mode Applier
  const applyAutoCorrections = async (
    sugs: SuggestionItem[],
    wordTokens: WordToken[],
    pageId: string,
    bookId?: string | null
  ) => {
    const toAutoApply = sugs.filter((s) => {
      const freq = s.details?.frequency || s.details?.count || s.details?.learned_frequency || 0;
      return s.confidence >= 0.9 && freq > 5;
    });

    if (toAutoApply.length === 0) return;

    for (const sug of toAutoApply) {
      const tokIdx = sug.index !== undefined 
        ? sug.index 
        : wordTokens.find((t) => (t.original_text || t.text) === sug.original)?.index;
      if (tokIdx === undefined) continue;

      setEditedWords((prev) => ({ ...prev, [tokIdx]: sug.suggested }));
      setTokens((prev) =>
        prev.map((t) => (t.index === tokIdx ? { ...t, text: sug.suggested, status: 'manually_confirmed' } : t))
      );

      try {
        await api.createCorrection({
          page_id: pageId,
          bbox: sug.bbox || [0, 0, 0, 0],
          ocr_text: sug.original,
          corrected_text: sug.suggested,
          engine: currentPage?.ocr_engine || 'tesseract',
          book_id: bookId || selectedBookId
        });
        showToast(`स्वतः सुधारा गया: ${sug.original} -> ${sug.suggested} (विश्वास ${Math.round(sug.confidence * 100)}%)`, 'learning');
      } catch (err) {
        console.warn('Auto correction failed', err);
      }
    }
  };

  // 4. Fetch intelligent suggestions for page
  const fetchSuggestions = async (pageId: string, wordTokens: WordToken[], bookId?: string | null) => {
    if (!pageId || wordTokens.length === 0) {
      setSuggestionsMap({});
      return;
    }
    setIsFetchingSuggestions(true);
    try {
      const res = await api.getPageSuggestions(pageId, wordTokens, bookId);
      if (res && res.suggestions) {
        const map: Record<number, SuggestionItem> = {};
        res.suggestions.forEach((sug) => {
          if (sug.index !== undefined && sug.index !== null) {
            map[sug.index] = sug;
          } else {
            const matchTok = wordTokens.find((t) => (t.original_text || t.text) === sug.original);
            if (matchTok) {
              map[matchTok.index] = sug;
            }
          }
        });
        setSuggestionsMap(map);

        if (correctionMode === 'auto') {
          applyAutoCorrections(res.suggestions, wordTokens, pageId, bookId);
        }
      }
    } catch (err) {
      console.warn('Failed to load page suggestions', err);
    } finally {
      setIsFetchingSuggestions(false);
    }
  };

  const loadPageData = (page: PageData) => {
    setCurrentPage(page);
    let parsedTokens: WordToken[] = [];
    if (Array.isArray(page.word_tokens)) {
      parsedTokens = page.word_tokens;
    } else if (typeof (page as any).word_tokens_json === 'string') {
      try {
        parsedTokens = JSON.parse((page as any).word_tokens_json);
      } catch {
        parsedTokens = [];
      }
    }

    // Fallback if no tokens: split verified/raw text into synthetic tokens
    if (parsedTokens.length === 0 && (page.verified_text || page.raw_ocr_text)) {
      const srcText = page.verified_text || page.raw_ocr_text || '';
      const words = srcText.trim().split(/\s+/);
      parsedTokens = words.map((w, idx) => ({
        index: idx,
        text: w,
        original_text: w,
        confidence: 90,
        confidence_tier: 'high' as const,
        bbox: [10 + (idx % 8) * 60, 20 + Math.floor(idx / 8) * 30, 50, 24] as [number, number, number, number],
        block_num: 1,
        par_num: 1,
        line_num: Math.floor(idx / 8) + 1,
        word_num: (idx % 8) + 1,
        flags: [],
        status: 'verified' as const
      }));
    }

    setTokens(parsedTokens);

    // Initialize edited words map
    const initialMap: Record<number, string> = {};
    parsedTokens.forEach((tok, i) => {
      initialMap[tok.index !== undefined ? tok.index : i] = tok.edited_text || tok.text || '';
    });
    setEditedWords(initialMap);
    setIgnoredSuggestions({});

    // Fetch live suggestions
    fetchSuggestions(page.id, parsedTokens, selectedBookId || page.book_id);
  };

  const handlePageChange = (newIndex: number) => {
    if (newIndex >= 0 && newIndex < pages.length) {
      setCurrentPageIndex(newIndex);
      loadPageData(pages[newIndex]);
      setSelectedWordIdx(null);
    }
  };

  // 5. User Edits Word and Blurs Input
  const handleWordBlur = async (tokenIdx: number, originalText: string, currentInput: string, bbox: any) => {
    const trimmedInput = currentInput.trim();
    const trimmedOriginal = (originalText || '').trim();

    // Only trigger learning if user actually changed the text
    if (!trimmedInput || trimmedInput === trimmedOriginal) {
      return;
    }

    if (!currentPage) return;

    try {
      // Call POST /api/corrections
      await api.createCorrection({
        page_id: currentPage.id,
        bbox: bbox || [0, 0, 0, 0],
        ocr_text: trimmedOriginal,
        corrected_text: trimmedInput,
        engine: currentPage.ocr_engine || 'tesseract',
        book_id: selectedBookId || currentPage.book_id
      });

      // Show Learning Toast as requested
      showToast(`सीखा गया: ${trimmedOriginal} -> ${trimmedInput}`, 'learning');

      // Increment learned count
      setLearnedCount((c) => c + 1);

      // Update local token
      setTokens((prev) =>
        prev.map((t, i) =>
          (t.index === tokenIdx || i === tokenIdx)
            ? { ...t, text: trimmedInput, status: 'manually_confirmed' }
            : t
        )
      );

      // Refresh suggestions
      fetchSuggestions(currentPage.id, tokens, selectedBookId || currentPage.book_id);

      // Refresh learned words list in background
      api.getLearnedWords(selectedBookId, 50).then((lw) => {
        if (lw && lw.words) {
          setLearnedWordsList(lw.words);
        }
      });
    } catch (err: any) {
      console.error('Correction submission failed', err);
      showToast(`सुधार सहेजने में विफल: ${err.message}`, 'error');
    }
  };

  // 6. User Clicks [Accept] on Suggestion Card
  const handleAcceptSuggestion = async (tokenIdx: number, sug: SuggestionItem, token: WordToken) => {
    if (!currentPage) return;

    setEditedWords((prev) => ({ ...prev, [tokenIdx]: sug.suggested }));

    try {
      await api.createCorrection({
        page_id: currentPage.id,
        bbox: token.bbox || sug.bbox || [0, 0, 0, 0],
        ocr_text: token.original_text || token.text,
        corrected_text: sug.suggested,
        engine: currentPage.ocr_engine || 'tesseract',
        book_id: selectedBookId || currentPage.book_id
      });

      showToast(`स्वीकृत एवं सीखा गया: ${sug.original} -> ${sug.suggested}`, 'learning');
      setLearnedCount((c) => c + 1);

      // Remove suggestion from active map
      setSuggestionsMap((prev) => {
        const next = { ...prev };
        delete next[tokenIdx];
        return next;
      });

      // Update local token status
      setTokens((prev) =>
        prev.map((t, i) =>
          (t.index === tokenIdx || i === tokenIdx)
            ? { ...t, text: sug.suggested, status: 'manually_confirmed' }
            : t
        )
      );

      // Refresh learned words in background
      api.getLearnedWords(selectedBookId, 50).then((lw) => {
        if (lw && lw.words) setLearnedWordsList(lw.words);
      });
    } catch (err: any) {
      showToast(`सुधार विफल: ${err.message}`, 'error');
    }
  };

  // 7. User Clicks [Ignore] on Suggestion Card
  const handleIgnoreSuggestion = (tokenIdx: number) => {
    setIgnoredSuggestions((prev) => ({ ...prev, [tokenIdx]: true }));
    showToast('सुझाव अनदेखा किया गया', 'success');
  };

  // Filtered tokens
  const visibleTokens = tokens.filter((tok) => {
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const matchText = (tok.text || '').toLowerCase().includes(q);
      const matchOrig = (tok.original_text || '').toLowerCase().includes(q);
      if (!matchText && !matchOrig) return false;
    }

    if (filterMode === 'flagged') {
      const isDisagreement = Boolean(tok.disagreement_type || tok.flags?.includes('DISAGREEMENT'));
      const isLowConf = tok.confidence < 70;
      const isAnomaly = Boolean(tok.unicode_anomalies && tok.unicode_anomalies.length > 0);
      const hasSug = Boolean(suggestionsMap[tok.index] && !ignoredSuggestions[tok.index]);
      return isDisagreement || isLowConf || isAnomaly || hasSug || tok.status === 'needs_review';
    }
    if (filterMode === 'verified') {
      return tok.status === 'verified' || tok.status === 'manually_confirmed';
    }
    return true;
  });

  const pageImageSrc = currentPage
    ? getStorageUrl(currentPage.adjusted_image_path || currentPage.optimized_image_path || currentPage.original_image_path)
    : '';

  return (
    <div className="flex flex-col min-h-screen bg-stone-100 font-devanagari">
      {/* Top Floating Learning Toasts */}
      <div className="fixed top-20 right-4 z-50 flex flex-col gap-2 max-w-sm pointer-events-none">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`px-4 py-3 rounded-2xl shadow-xl border flex items-center gap-3 animate-slide-in pointer-events-auto transition-all ${
              toast.type === 'learning'
                ? 'bg-vedic-900 text-white border-vedic-700/80 shadow-vedic-950/20'
                : toast.type === 'error'
                ? 'bg-red-900 text-white border-red-700 shadow-red-950/20'
                : 'bg-emerald-900 text-white border-emerald-700 shadow-emerald-950/20'
            }`}
          >
            <div className="w-8 h-8 rounded-xl bg-white/10 flex items-center justify-center shrink-0">
              <Sparkles className="w-4 h-4 text-amber-300 animate-spin-slow" />
            </div>
            <div className="text-sm font-semibold tracking-wide">
              {toast.text}
            </div>
          </div>
        ))}
      </div>

      {/* Header Bar */}
      <div className="bg-white border-b border-stone-200 px-4 sm:px-6 py-3.5 sticky top-0 z-30 shadow-xs flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          {onBackToBooks && (
            <button
              type="button"
              onClick={onBackToBooks}
              className="p-2 rounded-xl text-stone-500 hover:text-stone-900 hover:bg-stone-100 transition-colors cursor-pointer"
              title="पुस्तकों पर वापस जाएं"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
          )}

          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded-xl bg-vedic-100 text-vedic-800 flex items-center justify-center font-bold">
              <BrainCircuit className="w-5 h-5 text-vedic-700" />
            </div>
            <div>
              <h1 className="text-base sm:text-lg font-bold text-stone-900 flex items-center gap-2">
                <span>शब्द-दर-शब्द सत्यापन व शिक्षण (Live Learning)</span>
                <span className="px-2 py-0.5 rounded-full text-xs bg-amber-100 text-amber-900 font-semibold border border-amber-300">
                  {learnedCount} शब्द सीखे गए
                </span>
              </h1>
              <p className="text-xs text-stone-500">
                प्रत्येक सुधार सीधे AI मॉडल की स्मृति (Confusion Matrix व Learned Words) में दर्ज होता है
              </p>
            </div>
          </div>
        </div>

        {/* Book Selector & Page Navigator */}
        <div className="flex items-center gap-2 flex-wrap">
          {books.length > 0 && (
            <select
              value={selectedBookId || ''}
              onChange={(e) => setSelectedBookId(e.target.value)}
              className="px-3 py-1.5 rounded-xl border border-stone-300 bg-white text-xs font-semibold text-stone-800 shadow-2xs focus:ring-2 focus:ring-vedic-600 focus:outline-hidden"
            >
              {books.map((b) => (
                <option key={b.id} value={b.id}>
                  📖 {b.name} ({b.total_pages} पृष्ठ)
                </option>
              ))}
            </select>
          )}

          {/* Page Switcher */}
          {pages.length > 0 && (
            <div className="flex items-center gap-1 bg-stone-100 p-1 rounded-xl border border-stone-200">
              <button
                type="button"
                onClick={() => handlePageChange(currentPageIndex - 1)}
                disabled={currentPageIndex === 0}
                className="p-1 rounded-lg hover:bg-white text-stone-700 disabled:opacity-40 cursor-pointer"
                title="पिछला पृष्ठ"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>

              <span className="text-xs font-bold px-2 text-stone-800 font-sans">
                {currentPageIndex + 1} / {pages.length}
              </span>

              <button
                type="button"
                onClick={() => handlePageChange(currentPageIndex + 1)}
                disabled={currentPageIndex === pages.length - 1}
                className="p-1 rounded-lg hover:bg-white text-stone-700 disabled:opacity-40 cursor-pointer"
                title="अगला पृष्ठ"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}

          <button
            type="button"
            onClick={() => setShowLearnedModal(true)}
            className="px-3 py-1.5 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-300 text-xs font-bold flex items-center gap-1.5 transition-colors shadow-2xs cursor-pointer"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-700" />
            <span>सीखे गए शब्द ({learnedCount})</span>
          </button>

          {onOpenLearning && (
            <button
              type="button"
              onClick={() => onOpenLearning(selectedBookId || undefined)}
              className="px-3 py-1.5 rounded-xl bg-purple-50 hover:bg-purple-100 text-purple-900 border border-purple-300 text-xs font-bold flex items-center gap-1.5 transition-colors shadow-2xs cursor-pointer"
              title="एआई अधिगम डैशबोर्ड व मॉडल सांख्यिकी"
            >
              <Sparkles className="w-3.5 h-3.5 text-purple-700" />
              <span>एआई डैशबोर्ड</span>
            </button>
          )}

          {onNavigateToBuilder && selectedBookId && (
            <button
              type="button"
              onClick={() => onNavigateToBuilder(selectedBookId)}
              className="px-3 py-1.5 rounded-xl bg-vedic-700 hover:bg-vedic-800 text-white text-xs font-bold flex items-center gap-1.5 transition-colors shadow-xs cursor-pointer"
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span>ग्रन्थ सम्पादक</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Dual Workspace */}
      <div className="flex-1 max-w-7xl w-full mx-auto p-3 sm:p-4 grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column (5 Cols): Scanned Original Page Image with Interactive Word Highlighting */}
        <div className="lg:col-span-5 bg-white rounded-2xl border border-stone-200 shadow-sm flex flex-col overflow-hidden max-h-[82vh]">
          <div className="px-4 py-2.5 border-b border-stone-200 bg-stone-50 flex items-center justify-between">
            <span className="text-xs font-bold text-stone-700 flex items-center gap-1.5">
              <span>मूल पांडुलिपि पृष्ठ {currentPage?.page_number || currentPageIndex + 1}</span>
            </span>

            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setZoomLevel((z) => Math.max(0.75, z - 0.25))}
                className="p-1 text-stone-600 hover:bg-stone-200 rounded cursor-pointer"
                title="Zoom Out"
              >
                <ZoomOut className="w-3.5 h-3.5" />
              </button>
              <span className="text-[11px] font-mono font-semibold text-stone-500 w-10 text-center">
                {Math.round(zoomLevel * 100)}%
              </span>
              <button
                type="button"
                onClick={() => setZoomLevel((z) => Math.min(2.5, z + 0.25))}
                className="p-1 text-stone-600 hover:bg-stone-200 rounded cursor-pointer"
                title="Zoom In"
              >
                <ZoomIn className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <div 
            ref={imageContainerRef}
            className="flex-1 overflow-auto p-4 flex items-center justify-center bg-stone-900/5 select-none relative"
          >
            {isLoading ? (
              <div className="flex flex-col items-center gap-2 text-stone-400">
                <RefreshCw className="w-6 h-6 animate-spin text-vedic-600" />
                <span className="text-xs">पृष्ठ लोड हो रहा है...</span>
              </div>
            ) : pageImageSrc ? (
              <div className="relative inline-block transition-transform duration-150" style={{ transform: `scale(${zoomLevel})`, transformOrigin: 'center center' }}>
                <img
                  src={pageImageSrc}
                  alt={`Page ${currentPage?.page_number}`}
                  className="max-h-[70vh] w-auto rounded-lg shadow-md border border-stone-200 object-contain block"
                />

                {/* Word bounding boxes overlay */}
                {selectedWordIdx !== null && tokens[selectedWordIdx] && (
                  <div
                    className="absolute border-2 border-amber-500 bg-amber-400/20 rounded pointer-events-none transition-all duration-150 animate-pulse"
                    style={{
                      left: `${tokens[selectedWordIdx].bbox?.[0] || 0}px`,
                      top: `${tokens[selectedWordIdx].bbox?.[1] || 0}px`,
                      width: `${tokens[selectedWordIdx].bbox?.[2] || 40}px`,
                      height: `${tokens[selectedWordIdx].bbox?.[3] || 20}px`,
                    }}
                  />
                )}
              </div>
            ) : (
              <div className="text-xs text-stone-400">पृष्ठ छवि उपलब्ध नहीं है</div>
            )}
          </div>
        </div>

        {/* Right Column (7 Cols): Word-by-Word Live Learning Verification Cards */}
        <div className="lg:col-span-7 bg-white rounded-2xl border border-stone-200 shadow-sm flex flex-col overflow-hidden max-h-[82vh]">
          {/* Controls & Filter Bar with Mode Switcher */}
          <div className="p-3 border-b border-stone-200 bg-stone-50 flex flex-wrap items-center justify-between gap-2.5">
            <div className="flex items-center gap-1.5 flex-wrap">
              <button
                type="button"
                onClick={() => setFilterMode('all')}
                className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
                  filterMode === 'all'
                    ? 'bg-vedic-700 text-white shadow-2xs'
                    : 'bg-white border border-stone-200 text-stone-700 hover:bg-stone-100'
                }`}
              >
                सभी ({tokens.length})
              </button>

              <button
                type="button"
                onClick={() => setFilterMode('flagged')}
                className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-colors flex items-center gap-1 cursor-pointer ${
                  filterMode === 'flagged'
                    ? 'bg-amber-600 text-white shadow-2xs'
                    : 'bg-white border border-stone-200 text-amber-800 hover:bg-amber-50'
                }`}
              >
                <AlertTriangle className="w-3 h-3 text-amber-500" />
                <span>
                  संशयित/सुझाव (
                  {tokens.filter((t) => t.confidence < 70 || Boolean(t.disagreement_type) || Boolean(suggestionsMap[t.index] && !ignoredSuggestions[t.index])).length}
                  )
                </span>
              </button>

              <button
                type="button"
                onClick={() => setFilterMode('verified')}
                className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
                  filterMode === 'verified'
                    ? 'bg-emerald-700 text-white shadow-2xs'
                    : 'bg-white border border-stone-200 text-stone-700 hover:bg-stone-100'
                }`}
              >
                सत्यापित
              </button>
            </div>

            {/* Mode Switcher: Suggestion Mode vs Auto-Correct Mode */}
            <div className="flex items-center gap-2">
              <div className="flex items-center bg-stone-200/80 p-0.5 rounded-xl border border-stone-300/80 shadow-2xs">
                <button
                  type="button"
                  onClick={() => setCorrectionMode('suggestion')}
                  className={`px-2 py-1 rounded-lg text-[11px] font-bold flex items-center gap-1 transition-all cursor-pointer ${
                    correctionMode === 'suggestion'
                      ? 'bg-vedic-800 text-white shadow-xs'
                      : 'text-stone-700 hover:text-stone-900'
                  }`}
                  title="सुझाव मोड (अनुमोदन आवश्यक): उपयोगकर्ता प्रत्येक सुझाव को स्वीकार या अनदेखा करेगा"
                >
                  <Lightbulb className="w-3 h-3" />
                  <span>सुझाव मोड</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setCorrectionMode('auto');
                    if (currentPage && tokens.length > 0) {
                      applyAutoCorrections(Object.values(suggestionsMap), tokens, currentPage.id, selectedBookId);
                    }
                  }}
                  className={`px-2 py-1 rounded-lg text-[11px] font-bold flex items-center gap-1 transition-all cursor-pointer ${
                    correctionMode === 'auto'
                      ? 'bg-amber-600 text-white shadow-xs'
                      : 'text-stone-700 hover:text-stone-900'
                  }`}
                  title="Auto-Correct Mode: आवृत्ति > 5 एवं विश्वास > 90% वाले शब्दों को स्वतः ठीक किया जाएगा"
                >
                  <Zap className="w-3 h-3 text-amber-300" />
                  <span>Auto-Correct</span>
                </button>
              </div>

              {/* Quick Word Search */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-stone-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="शब्द खोजें..."
                  className="pl-8 pr-3 py-1 rounded-xl border border-stone-300 text-xs bg-white text-stone-800 w-32 sm:w-40 focus:ring-1 focus:ring-vedic-600 focus:outline-hidden"
                />
              </div>
            </div>
          </div>

          {/* Word Grid / Cards List */}
          <div className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-2.5">
            {isFetchingSuggestions && (
              <div className="p-2 bg-amber-50/60 border border-amber-200/80 rounded-xl flex items-center gap-2 text-xs text-amber-800">
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-amber-600" />
                <span>AI सुझाव विश्लेषित हो रहे हैं...</span>
              </div>
            )}

            {visibleTokens.length === 0 ? (
              <div className="py-16 text-center text-stone-400 text-sm">
                कोई शब्द नहीं मिला
              </div>
            ) : (
              visibleTokens.map((token, idx) => {
                const currentVal = editedWords[token.index] !== undefined ? editedWords[token.index] : token.text;
                const isEdited = currentVal.trim() !== (token.original_text || token.text).trim();
                const isSelected = selectedWordIdx === token.index;
                const isLowConf = token.confidence < 70;

                const sug = suggestionsMap[token.index];
                const hasActiveSuggestion = Boolean(sug && !ignoredSuggestions[token.index] && currentVal.trim() !== sug.suggested);

                return (
                  <div
                    key={`${token.index}_${idx}`}
                    onClick={() => setSelectedWordIdx(token.index)}
                    className={`p-3 rounded-xl border transition-all ${
                      isSelected
                        ? 'border-vedic-500 bg-vedic-50/50 shadow-sm'
                        : hasActiveSuggestion
                        ? 'border-amber-300 bg-amber-50/30 shadow-2xs'
                        : isEdited
                        ? 'border-emerald-300 bg-emerald-50/30'
                        : isLowConf
                        ? 'border-amber-200 bg-amber-50/20'
                        : 'border-stone-200 bg-white hover:border-stone-300'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      {/* Left: Metadata & Original OCR */}
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span className="w-6 h-6 rounded-md bg-stone-100 border border-stone-200 text-stone-600 text-[11px] font-mono flex items-center justify-center shrink-0">
                          {token.index + 1}
                        </span>

                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="text-xs text-stone-400 font-mono">OCR:</span>
                            <span 
                              className={`text-sm font-semibold text-stone-900 font-devanagari ${
                                hasActiveSuggestion ? 'underline decoration-amber-500 decoration-wavy decoration-2 underline-offset-4' : ''
                              }`}
                              title={hasActiveSuggestion ? `सुझाव उपलब्ध: ${sug?.suggested}` : ''}
                            >
                              {token.original_text || token.text}
                            </span>
                            {hasActiveSuggestion && (
                              <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-amber-100 text-amber-800 border border-amber-300 font-bold flex items-center gap-0.5">
                                <Sparkles className="w-2.5 h-2.5 text-amber-600" />
                                <span>सुझाव</span>
                              </span>
                            )}
                          </div>

                          <div className="flex items-center gap-2 mt-0.5 text-[10px] text-stone-500">
                            <span>विश्वास: {token.confidence}%</span>
                            {token.disagreement_type && (
                              <span className="text-amber-700 font-semibold">⚠️ भिन्नता</span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Right: Editable Input with onBlur learning hook */}
                      <div className="flex items-center gap-2">
                        <div className="flex flex-col items-end">
                          <input
                            type="text"
                            value={currentVal}
                            onChange={(e) => {
                              const val = e.target.value;
                              setEditedWords((prev) => ({ ...prev, [token.index]: val }));
                            }}
                            onBlur={() => {
                              handleWordBlur(
                                token.index,
                                token.original_text || token.text,
                                currentVal,
                                token.bbox
                              );
                            }}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                (e.target as HTMLInputElement).blur();
                              }
                            }}
                            className={`px-3 py-1.5 rounded-lg border text-sm font-bold font-devanagari text-stone-900 w-32 sm:w-44 focus:outline-hidden transition-all shadow-2xs ${
                              isEdited
                                ? 'border-emerald-500 bg-emerald-50 focus:ring-2 focus:ring-emerald-400'
                                : hasActiveSuggestion
                                ? 'border-amber-400 bg-amber-50/70 focus:border-amber-600 focus:ring-2 focus:ring-amber-300'
                                : 'border-stone-300 bg-stone-50/50 focus:bg-white focus:border-vedic-600 focus:ring-2 focus:ring-vedic-400'
                            }`}
                            placeholder="सत्यापित पाठ दर्ज करें"
                          />
                          {isEdited && (
                            <span className="text-[10px] text-emerald-700 font-bold mt-0.5 flex items-center gap-0.5">
                              <Check className="w-3 h-3 text-emerald-600" />
                              सीखा हुआ
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Active Suggestion Tooltip Card */}
                    {hasActiveSuggestion && sug && (
                      <div className="mt-2.5 p-2.5 rounded-xl bg-amber-50 border border-amber-300 text-xs font-devanagari animate-fade-in shadow-2xs">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex items-center gap-1.5 text-amber-950 font-medium">
                            <Sparkles className="w-4 h-4 text-amber-600 shrink-0" />
                            <span>
                              {sug.reason || `आपने पहले ${sug.details?.count || 1} बार '${sug.original}' को '${sug.suggested}' ठीक किया था। बदलें?`}
                            </span>
                          </div>
                          <span className="text-[10px] px-1.5 py-0.5 rounded-md bg-amber-200/80 text-amber-900 font-bold shrink-0 font-sans">
                            {Math.round(sug.confidence * 100)}% विश्वास
                          </span>
                        </div>

                        <div className="flex items-center justify-end gap-2 mt-2 pt-2 border-t border-amber-200/70">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleIgnoreSuggestion(token.index);
                            }}
                            className="px-2.5 py-1 rounded-lg bg-white hover:bg-stone-100 text-stone-700 border border-stone-300 text-xs font-semibold flex items-center gap-1 cursor-pointer transition-colors"
                          >
                            <X className="w-3 h-3 text-stone-500" />
                            <span>अनदेखा करें</span>
                          </button>

                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAcceptSuggestion(token.index, sug, token);
                            }}
                            className="px-3 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white text-xs font-bold flex items-center gap-1 cursor-pointer transition-colors shadow-2xs"
                          >
                            <Check className="w-3.5 h-3.5" />
                            <span>स्वीकारें ('{sug.suggested}')</span>
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* Learned Words Modal Drawer */}
      {showLearnedModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-stone-950/70 backdrop-blur-xs animate-fade-in"
          onClick={() => setShowLearnedModal(false)}
        >
          <div
            className="bg-white rounded-2xl max-w-xl w-full p-5 shadow-2xl border border-stone-200 max-h-[85vh] flex flex-col animate-scale-up"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between pb-3 border-b border-stone-200">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-amber-600" />
                <h3 className="font-bold text-stone-900 text-base">
                  सीखे गए शब्द भंडार (Learned Vocabulary)
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowLearnedModal(false)}
                className="text-stone-400 hover:text-stone-700 p-1 rounded-lg cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto py-3 space-y-2">
              {learnedWordsList.length === 0 ? (
                <div className="py-8 text-center text-stone-400 text-xs">
                  अभी तक कोई शब्द नहीं सीखा गया है। शब्दों को सुधारते ही वे यहाँ जुड़ते जाएंगे।
                </div>
              ) : (
                learnedWordsList.map((lw, i) => (
                  <div
                    key={lw.id || i}
                    className="p-2.5 rounded-xl bg-stone-50 border border-stone-200 flex items-center justify-between text-xs"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-stone-900 text-sm font-devanagari">
                        {lw.word}
                      </span>
                    </div>
                    <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-bold font-sans">
                      {lw.frequency} बार सत्यापित
                    </span>
                  </div>
                ))
              )}
            </div>

            <div className="pt-3 border-t border-stone-200 flex justify-end">
              <button
                type="button"
                onClick={() => setShowLearnedModal(false)}
                className="px-4 py-1.5 rounded-xl bg-stone-800 hover:bg-stone-900 text-white text-xs font-bold cursor-pointer"
              >
                बंद करें
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
export default Verify;
