import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  BookOpen, Search, ArrowLeft, ChevronLeft, ChevronRight,
  Copy, Check, Image as ImageIcon, X, ZoomIn, ZoomOut, RotateCcw,
  Eye, Filter, RefreshCw, AlertCircle,
  Sparkles, Layers, BookMarked, Home
} from 'lucide-react';
import { api, getStorageUrl } from '../services/api';
import type { BhajanItem, BhajanSearchFilter, BookData } from '../types';
import type { Language } from '../i18n/translations';

interface LibraryProps {
  bookId?: string;
  lang?: Language;
  onNavigateBack?: () => void;
  onNavigateHome?: () => void;
  onOpenBookBuilder?: (bookId: string) => void;
}

export const Library: React.FC<LibraryProps> = ({
  bookId: propBookId,
  lang = 'hi',
  onNavigateBack,
  onNavigateHome,
  onOpenBookBuilder
}) => {
  const isHi = lang === 'hi';

  // Selected Book state
  const [books, setBooks] = useState<BookData[]>([]);
  const [selectedBookId, setSelectedBookId] = useState<string>(propBookId || '');
  const [currentBook, setCurrentBook] = useState<BookData | null>(null);

  // Bhajans & Search state
  const [bhajans, setBhajans] = useState<BhajanItem[]>([]);
  const [filteredBhajans, setFilteredBhajans] = useState<BhajanItem[]>([]);
  const [selectedBhajanId, setSelectedBhajanId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searchFilter, setSearchFilter] = useState<BhajanSearchFilter>('all');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Reading Typography Controls
  const [fontFamily, setFontFamily] = useState<'noto' | 'mangal' | 'martel'>('noto');
  const [fontSize, setFontSize] = useState<number>(18); // px
  const [lineHeight, setLineHeight] = useState<number>(1.8);
  const [copiedBhajanId, setCopiedBhajanId] = useState<string | null>(null);

  // Original Manuscript Scan Drawer / Modal
  const [isScanDrawerOpen, setIsScanDrawerOpen] = useState<boolean>(false);
  const [imageZoom, setImageZoom] = useState<number>(1);
  const [imageRotation, setImageRotation] = useState<number>(0);

  const searchInputRef = useRef<HTMLInputElement>(null);

  // 1. Initial Load: Fetch book list if no bookId provided or to support switching
  useEffect(() => {
    const fetchBooks = async () => {
      try {
        const res = await api.listBooks();
        if (res && res.books && res.books.length > 0) {
          setBooks(res.books);
          if (!selectedBookId) {
            setSelectedBookId(res.books[0].id);
          }
        }
      } catch (err) {
        console.error('Failed to list books:', err);
      }
    };
    fetchBooks();
  }, []);

  // Update selectedBookId when prop changes
  useEffect(() => {
    if (propBookId) {
      setSelectedBookId(propBookId);
    }
  }, [propBookId]);

  // 2. Fetch Bhajans whenever selectedBookId changes
  useEffect(() => {
    if (!selectedBookId) return;

    const loadBookAndBhajans = async () => {
      try {
        setIsLoading(true);
        setErrorMsg(null);

        // Fetch book details
        try {
          const bRes = await api.getBook(selectedBookId);
          if (bRes && bRes.book) {
            setCurrentBook(bRes.book);
          }
        } catch {
          // Fallback if getBook fails
        }

        // Fetch bhajans parsed from combined text
        const res = await api.getBookBhajans(selectedBookId);
        if (res && res.bhajans) {
          setBhajans(res.bhajans);
          setFilteredBhajans(res.bhajans);
          if (res.bhajans.length > 0) {
            setSelectedBhajanId(res.bhajans[0].id);
          } else {
            setSelectedBhajanId(null);
          }
        } else {
          setBhajans([]);
          setFilteredBhajans([]);
          setSelectedBhajanId(null);
        }
      } catch (err: any) {
        console.error('Failed to load bhajans:', err);
        setErrorMsg(err.message || (isHi ? 'भजन सूची लोड करने में त्रुटि हुई।' : 'Failed to load bhajans.'));
        setBhajans([]);
        setFilteredBhajans([]);
      } finally {
        setIsLoading(false);
      }
    };

    loadBookAndBhajans();
  }, [selectedBookId, isHi]);

  // 3. Search handling with FTS5 backend call or local filtering
  useEffect(() => {
    if (!selectedBookId) return;

    if (!searchQuery.trim()) {
      setFilteredBhajans(bhajans);
      if (bhajans.length > 0 && (!selectedBhajanId || !bhajans.some(b => b.id === selectedBhajanId))) {
        setSelectedBhajanId(bhajans[0].id);
      }
      return;
    }

    const timer = setTimeout(async () => {
      try {
        setIsSearching(true);
        const res = await api.searchBookBhajans(selectedBookId, searchQuery.trim(), searchFilter);
        if (res && res.bhajans) {
          setFilteredBhajans(res.bhajans);
          if (res.bhajans.length > 0) {
            setSelectedBhajanId(res.bhajans[0].id);
          }
        }
      } catch (err) {
        console.error('Backend search error, falling back to local filter:', err);
        // Fallback local search
        const q = searchQuery.toLowerCase().trim();
        const localMatches = bhajans.filter(b => {
          if (searchFilter === 'number') {
            return b.bhajan_number.toString() === q;
          }
          if (searchFilter === 'title') {
            return b.title.toLowerCase().includes(q);
          }
          if (searchFilter === 'content') {
            return b.text.toLowerCase().includes(q);
          }
          if (searchFilter === 'starting_lines') {
            return b.starting_lines.toLowerCase().includes(q);
          }
          return (
            b.bhajan_number.toString() === q ||
            b.title.toLowerCase().includes(q) ||
            b.text.toLowerCase().includes(q) ||
            b.starting_lines.toLowerCase().includes(q)
          );
        });
        setFilteredBhajans(localMatches);
        if (localMatches.length > 0) {
          setSelectedBhajanId(localMatches[0].id);
        }
      } finally {
        setIsSearching(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [searchQuery, searchFilter, selectedBookId, bhajans]);

  // Active Bhajan object
  const activeBhajan = useMemo(() => {
    return filteredBhajans.find(b => b.id === selectedBhajanId) || bhajans.find(b => b.id === selectedBhajanId) || null;
  }, [filteredBhajans, bhajans, selectedBhajanId]);

  // Current index for next/prev navigation
  const activeIndex = useMemo(() => {
    if (!activeBhajan) return -1;
    return filteredBhajans.findIndex(b => b.id === activeBhajan.id);
  }, [filteredBhajans, activeBhajan]);

  // Next / Previous navigation
  const handlePrevBhajan = () => {
    if (activeIndex > 0) {
      setSelectedBhajanId(filteredBhajans[activeIndex - 1].id);
    }
  };

  const handleNextBhajan = () => {
    if (activeIndex >= 0 && activeIndex < filteredBhajans.length - 1) {
      setSelectedBhajanId(filteredBhajans[activeIndex + 1].id);
    }
  };

  // Copy Bhajan text to clipboard
  const handleCopyText = async (textToCopy: string, bhajanId: string) => {
    try {
      await navigator.clipboard.writeText(textToCopy);
      setCopiedBhajanId(bhajanId);
      setTimeout(() => setCopiedBhajanId(null), 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };

  // Font family CSS class
  const getFontFamilyClass = () => {
    switch (fontFamily) {
      case 'mangal':
        return 'font-mangal';
      case 'martel':
        return 'font-traditional';
      default:
        return 'font-devanagari';
    }
  };

  // Helper for title display obeying the strict "No Auto-Naming" rule
  const renderBhajanTitle = (title: string, customClass = 'font-bold') => {
    const isUnknown = !title || title.trim().toLowerCase() === 'unknown' || title.trim().toLowerCase() === 'pending';
    if (isUnknown) {
      return (
        <span className="inline-flex items-center gap-1.5 text-stone-500 italic font-medium">
          <span className="not-italic text-stone-400">॥</span>
          <span>{isHi ? 'अज्ञात शीर्षक' : 'Unknown Title'}</span>
          <span className="not-italic text-stone-400">॥</span>
        </span>
      );
    }
    return <span className={customClass}>{title}</span>;
  };

  return (
    <div className="min-h-screen bg-[#faf8f5] flex flex-col text-stone-900 font-sans">
      {/* Top Navigation Header */}
      <header className="sticky top-0 z-20 bg-white/95 backdrop-blur-md border-b border-stone-200/90 shadow-2xs">
        <div className="max-w-7xl w-full mx-auto px-3 sm:px-6 lg:px-8 h-16 sm:h-18 flex items-center justify-between gap-3">
          {/* Back & Title Section */}
          <div className="flex items-center gap-2 sm:gap-3.5 min-w-0">
            {onNavigateBack && (
              <button
                type="button"
                onClick={onNavigateBack}
                className="p-2 rounded-xl border border-stone-200 text-stone-600 hover:text-stone-900 hover:bg-stone-100 transition-colors shrink-0"
                title={isHi ? 'पीछे जाएँ' : 'Go Back'}
                aria-label={isHi ? 'पीछे जाएँ' : 'Go Back'}
              >
                <ArrowLeft className="w-4 h-4" />
              </button>
            )}
            {onNavigateHome && (
              <button
                type="button"
                onClick={onNavigateHome}
                className="p-2 rounded-xl border border-stone-200 text-stone-600 hover:text-stone-900 hover:bg-stone-100 transition-colors shrink-0"
                title={isHi ? 'मुख्य पृष्ठ' : 'Home'}
                aria-label={isHi ? 'मुख्य पृष्ठ' : 'Home'}
              >
                <Home className="w-4 h-4" />
              </button>
            )}

            <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-tr from-vedic-700 to-amber-600 p-0.5 shadow-2xs flex items-center justify-center shrink-0 text-white">
              <BookMarked className="w-5 h-5" />
            </div>

            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-base sm:text-lg font-bold font-devanagari text-vedic-950 truncate">
                  {currentBook?.name || (isHi ? 'ग्रन्थ पुस्तकालय' : 'Book Library')}
                </h1>
                <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-300 shrink-0">
                  <Sparkles className="w-3 h-3 text-amber-600" />
                  <span>{isHi ? 'डिजिटल ग्रन्थागार' : 'Heritage Reader'}</span>
                </span>
              </div>
              <p className="text-[11px] text-stone-500 font-devanagari truncate">
                {isHi ? 'पाण्डुलिपि से संकलित एवं सत्यापित भजनों का पवित्र संग्रह' : 'Preserved bhajans extracted from manuscript'}
              </p>
            </div>
          </div>

          {/* Book Switcher & Builder Shortcut */}
          <div className="flex items-center gap-2 shrink-0">
            {books.length > 1 && (
              <select
                value={selectedBookId}
                onChange={(e) => setSelectedBookId(e.target.value)}
                className="text-xs font-devanagari bg-stone-100 border border-stone-300 rounded-xl px-2.5 py-1.5 text-stone-800 focus:outline-hidden focus:ring-2 focus:ring-vedic-500 max-w-[140px] sm:max-w-[200px] truncate"
              >
                {books.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            )}

            {onOpenBookBuilder && selectedBookId && (
              <button
                type="button"
                onClick={() => onOpenBookBuilder(selectedBookId)}
                className="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-vedic-50 hover:bg-vedic-100 text-vedic-800 border border-vedic-300 font-bold text-xs font-devanagari transition-colors shadow-2xs"
                title={isHi ? 'पुस्तक संकलक में खोलें' : 'Open in Book Builder'}
              >
                <Layers className="w-3.5 h-3.5 text-vedic-700" />
                <span>{isHi ? 'संकलक में संपादन' : 'Edit in Builder'}</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Library Workspace */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 flex flex-col gap-4">
        {/* Error Notification */}
        {errorMsg && (
          <div className="p-3.5 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-devanagari flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{errorMsg}</span>
            </div>
            <button type="button" onClick={() => setErrorMsg(null)} className="text-rose-500 hover:text-rose-800">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Search Bar & Filter Strip */}
        <div className="bg-white rounded-2xl border border-stone-200/90 p-3 sm:p-4 shadow-2xs flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
          {/* Search Input */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-stone-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              ref={searchInputRef}
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={isHi ? "भजन क्रमांक, शीर्षक, शब्द (जैसे: गणेश, गोविन्द, जय) खोजें..." : "Search bhajan number, title, verse..."}
              className="w-full pl-10 pr-10 py-2.5 rounded-xl border border-stone-200 bg-stone-50/50 hover:bg-stone-50 focus:bg-white text-xs sm:text-sm font-devanagari focus:outline-hidden focus:ring-2 focus:ring-vedic-500 focus:border-transparent transition-all"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-stone-400 hover:text-stone-700"
                title={isHi ? 'खोज साफ़ करें' : 'Clear search'}
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
            {isSearching && (
              <RefreshCw className="w-3.5 h-3.5 text-vedic-600 animate-spin absolute right-10 top-1/2 -translate-y-1/2" />
            )}
          </div>

          {/* Filter Pills */}
          <div className="flex items-center gap-1.5 flex-wrap overflow-x-auto pb-1 md:pb-0">
            <span className="text-[11px] font-semibold text-stone-400 font-devanagari flex items-center gap-1 mr-1">
              <Filter className="w-3 h-3" />
              <span>{isHi ? 'फ़िल्टर:' : 'Filter:'}</span>
            </span>

            {[
              { id: 'all', labelHi: 'सभी', labelEn: 'All' },
              { id: 'title', labelHi: 'शीर्षक', labelEn: 'Title' },
              { id: 'number', labelHi: 'क्रमांक', labelEn: 'Number' },
              { id: 'content', labelHi: 'पाठ / शब्द', labelEn: 'Content' },
              { id: 'starting_lines', labelHi: 'आरंभिक पंक्तियाँ', labelEn: 'Starting Lines' }
            ].map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setSearchFilter(f.id as BhajanSearchFilter)}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-devanagari transition-all ${
                  searchFilter === f.id
                    ? 'bg-vedic-700 text-white font-bold shadow-2xs'
                    : 'bg-stone-100 hover:bg-stone-200 text-stone-600 font-medium'
                }`}
              >
                {isHi ? f.labelHi : f.labelEn}
              </button>
            ))}

            <span className="text-[11px] text-stone-500 font-devanagari ml-auto pl-2">
              {filteredBhajans.length} {isHi ? 'भजन' : 'bhajans'}
            </span>
          </div>
        </div>

        {/* Content Layout: Left (Bhajan List 35%) & Right (Reading Interface 65%) */}
        {isLoading ? (
          <div className="p-12 text-center bg-white rounded-3xl border border-stone-200/90 shadow-2xs my-4 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-8 h-8 animate-spin text-vedic-700" />
            <span className="text-sm font-semibold text-vedic-950 font-devanagari">
              {isHi ? 'पाण्डुलिपि से भजन सूची एवं मूल पाठ संकलित किया जा रहा है...' : 'Extracting bhajans and text from manuscript...'}
            </span>
          </div>
        ) : bhajans.length === 0 ? (
          <div className="p-8 sm:p-14 text-center bg-white rounded-3xl border border-stone-200/90 shadow-2xs max-w-xl mx-auto my-8">
            <div className="w-16 h-16 rounded-2xl bg-amber-50 border border-amber-200 text-amber-700 flex items-center justify-center mx-auto mb-4 font-traditional font-bold text-2xl shadow-2xs">
              भ
            </div>
            <h3 className="text-lg font-bold text-stone-900 font-devanagari mb-1">
              {isHi ? 'इस ग्रन्थ में अभी कोई भजन उपलब्ध नहीं है' : 'No Bhajans Available In This Book Yet'}
            </h3>
            <p className="text-xs sm:text-sm text-stone-500 font-devanagari mb-6 max-w-sm mx-auto">
              {isHi
                ? 'कृपया पुस्तक संकलक (Book Builder) में जाकर सत्यापित पृष्ठों को पुस्तक में जोड़ें अथवा पृष्ठों का सत्यापन पूर्ण करें।'
                : 'Please use the Book Builder to add verified manuscript pages to this book.'}
            </p>
            {onOpenBookBuilder && selectedBookId && (
              <button
                type="button"
                onClick={() => onOpenBookBuilder(selectedBookId)}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-vedic-700 hover:bg-vedic-800 text-white font-bold text-sm shadow-xs font-devanagari transition-colors"
              >
                <Layers className="w-4 h-4" />
                <span>{isHi ? 'पुस्तक संकलक खोलें' : 'Open Book Builder'}</span>
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
            {/* Left Panel: Bhajan List (4 of 12 cols = ~33%) */}
            <div className="lg:col-span-4 bg-white rounded-2xl border border-stone-200/90 shadow-2xs overflow-hidden flex flex-col max-h-[750px]">
              {/* Header */}
              <div className="p-3.5 border-b border-stone-100 bg-stone-50/60 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <BookOpen className="w-4 h-4 text-vedic-700" />
                  <span className="text-xs font-bold text-stone-800 font-devanagari">
                    {isHi ? 'भजन अनुक्रमणिका' : 'Index of Bhajans'}
                  </span>
                </div>
                <span className="text-[11px] font-semibold text-stone-500 font-devanagari bg-stone-200/60 px-2 py-0.5 rounded-full">
                  {filteredBhajans.length} {isHi ? 'प्रविष्टियाँ' : 'entries'}
                </span>
              </div>

              {/* Scrollable List */}
              <div className="flex-1 overflow-y-auto divide-y divide-stone-100 p-1.5 space-y-1">
                {filteredBhajans.length === 0 ? (
                  <div className="p-8 text-center text-stone-400 font-devanagari text-xs">
                    {isHi ? 'खोज के अनुसार कोई भजन नहीं मिला।' : 'No matching bhajans found.'}
                  </div>
                ) : (
                  filteredBhajans.map((b) => {
                    const isSelected = b.id === activeBhajan?.id;
                    const isUnknownTitle = !b.title || b.title.trim().toLowerCase() === 'unknown' || b.title.trim().toLowerCase() === 'pending';

                    return (
                      <div
                        key={b.id}
                        onClick={() => setSelectedBhajanId(b.id)}
                        className={`p-3 rounded-xl cursor-pointer transition-all text-left flex flex-col gap-1.5 ${
                          isSelected
                            ? 'bg-vedic-50/90 border border-vedic-300 shadow-2xs'
                            : 'hover:bg-stone-50 border border-transparent'
                        }`}
                      >
                        {/* Top row: Number and Page tag */}
                        <div className="flex items-center justify-between gap-2">
                          <span className={`inline-flex items-center gap-1 text-xs font-bold font-devanagari px-2 py-0.5 rounded-md ${
                            isSelected ? 'bg-vedic-700 text-white' : 'bg-amber-100 text-amber-900'
                          }`}>
                            <span>भजन {b.bhajan_number}</span>
                          </span>

                          <span className="text-[10px] font-medium text-stone-500 font-devanagari bg-stone-100 px-1.5 py-0.5 rounded">
                            पृष्ठ {b.original_page_number}
                          </span>
                        </div>

                        {/* Title (STRICT: "अज्ञात शीर्षक" when unknown, NEVER invented) */}
                        <div className="font-devanagari text-xs text-stone-900 line-clamp-1">
                          {renderBhajanTitle(b.title, 'font-bold text-stone-900')}
                          {isUnknownTitle && (
                            <span className="text-[10px] ml-1.5 text-stone-400 bg-stone-100 px-1.5 py-0.2 rounded border border-stone-200">
                              {isHi ? 'शीर्षक अप्राप्त' : 'No Title'}
                            </span>
                          )}
                        </div>

                        {/* Starting Lines Snippet */}
                        {b.starting_lines && (
                          <p className="text-[11px] text-stone-500 font-devanagari line-clamp-2 leading-relaxed italic bg-white/60 p-1.5 rounded-lg border border-stone-100">
                            "{b.starting_lines.replace(/\n/g, ' ')}"
                          </p>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Right Panel: Reading Interface (8 of 12 cols = ~67%) */}
            <div className="lg:col-span-8 bg-white rounded-2xl border border-stone-200/90 shadow-2xs overflow-hidden flex flex-col">
              {activeBhajan ? (
                <>
                  {/* Reading Toolbar */}
                  <div className="p-3 sm:p-4 border-b border-stone-100 bg-[#fdfbf7] flex flex-wrap items-center justify-between gap-3">
                    {/* Bhajan Header Details */}
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-1 rounded-lg bg-vedic-700 text-white font-bold text-xs font-devanagari shadow-2xs">
                        भजन क्रमांक {activeBhajan.bhajan_number}
                      </span>
                      <span className="text-xs text-stone-500 font-devanagari bg-stone-100 px-2 py-1 rounded-lg border border-stone-200">
                        मूल पाण्डुलिपि पृष्ठ {activeBhajan.original_page_number}
                      </span>
                    </div>

                    {/* Toolbar Actions */}
                    <div className="flex items-center gap-2 flex-wrap ml-auto">
                      {/* View Original Scanned Manuscript Page Button */}
                      <button
                        type="button"
                        onClick={() => {
                          setImageZoom(1);
                          setImageRotation(0);
                          setIsScanDrawerOpen(true);
                        }}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white font-bold text-xs font-devanagari transition-colors shadow-2xs"
                        title={isHi ? 'मूल पाण्डुलिपि पृष्ठ देखें' : 'View Original Manuscript Scan'}
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>{isHi ? 'मूल पाण्डुलिपि पृष्ठ देखें' : 'View Original Scan'}</span>
                      </button>

                      {/* Font Family Selector */}
                      <div className="inline-flex items-center bg-stone-100 p-0.5 rounded-lg border border-stone-200 text-xs font-devanagari">
                        <button
                          type="button"
                          onClick={() => setFontFamily('noto')}
                          className={`px-2 py-1 rounded-md transition-colors ${
                            fontFamily === 'noto' ? 'bg-white font-bold text-vedic-950 shadow-2xs' : 'text-stone-600'
                          }`}
                          title="Noto Sans Devanagari"
                        >
                          साधारण
                        </button>
                        <button
                          type="button"
                          onClick={() => setFontFamily('martel')}
                          className={`px-2 py-1 rounded-md transition-colors ${
                            fontFamily === 'martel' ? 'bg-white font-bold text-vedic-950 shadow-2xs' : 'text-stone-600'
                          }`}
                          title="Martel Traditional Serif"
                        >
                          पारम्परिक
                        </button>
                      </div>

                      {/* Font Size A- / A+ */}
                      <div className="inline-flex items-center bg-stone-100 p-0.5 rounded-lg border border-stone-200 text-xs">
                        <button
                          type="button"
                          onClick={() => setFontSize(s => Math.max(14, s - 2))}
                          className="px-2 py-1 hover:bg-white rounded text-stone-700 font-bold"
                          title="छोटा अक्षर (Smaller font)"
                        >
                          A-
                        </button>
                        <span className="px-1.5 text-[11px] font-mono text-stone-600">{fontSize}</span>
                        <button
                          type="button"
                          onClick={() => setFontSize(s => Math.min(32, s + 2))}
                          className="px-2 py-1 hover:bg-white rounded text-stone-700 font-bold"
                          title="बड़ा अक्षर (Larger font)"
                        >
                          A+
                        </button>
                      </div>

                      {/* Line Spacing */}
                      <div className="inline-flex items-center bg-stone-100 p-0.5 rounded-lg border border-stone-200 text-xs">
                        <button
                          type="button"
                          onClick={() => setLineHeight(h => (h === 1.5 ? 1.8 : h === 1.8 ? 2.2 : 1.5))}
                          className="px-2 py-1 hover:bg-white rounded text-stone-700 font-bold font-devanagari"
                          title="पंक्ति अंतराल (Line height)"
                        >
                          {lineHeight}x
                        </button>
                      </div>

                      {/* Copy Bhajan Text Button */}
                      <button
                        type="button"
                        onClick={() => handleCopyText(activeBhajan.text, activeBhajan.id)}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-stone-100 hover:bg-stone-200 text-stone-700 font-medium text-xs font-devanagari transition-colors"
                        title={isHi ? 'भजन पाठ कॉपी करें' : 'Copy Bhajan Text'}
                      >
                        {copiedBhajanId === activeBhajan.id ? (
                          <>
                            <Check className="w-3.5 h-3.5 text-emerald-600" />
                            <span className="text-emerald-700 font-bold">{isHi ? 'कॉपी हुआ!' : 'Copied!'}</span>
                          </>
                        ) : (
                          <>
                            <Copy className="w-3.5 h-3.5 text-stone-600" />
                            <span>{isHi ? 'कॉपी' : 'Copy'}</span>
                          </>
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Devotional Reading Body */}
                  <div className="p-6 sm:p-10 flex-1 overflow-y-auto bg-[#faf8f5]/40 min-h-[480px]">
                    <div className="max-w-2xl mx-auto bg-white p-6 sm:p-10 rounded-2xl border border-amber-200/60 shadow-xs relative">
                      {/* Traditional Corner Accents */}
                      <div className="absolute top-3 left-3 w-4 h-4 border-t-2 border-l-2 border-amber-500/40" />
                      <div className="absolute top-3 right-3 w-4 h-4 border-t-2 border-r-2 border-amber-500/40" />
                      <div className="absolute bottom-3 left-3 w-4 h-4 border-b-2 border-l-2 border-amber-500/40" />
                      <div className="absolute bottom-3 right-3 w-4 h-4 border-b-2 border-r-2 border-amber-500/40" />

                      {/* Devotional Heading */}
                      <div className="text-center mb-8 pb-4 border-b border-amber-200/40">
                        <span className="text-amber-800 font-devanagari text-xs tracking-widest block uppercase mb-1">
                          ॥ श्री हरिः ॥
                        </span>
                        <h2 className={`text-xl sm:text-2xl text-vedic-950 tracking-wide font-devanagari ${
                          !activeBhajan.title || activeBhajan.title === 'unknown' ? 'italic text-stone-600' : 'font-bold'
                        }`}>
                          {renderBhajanTitle(activeBhajan.title, 'font-bold text-vedic-950')}
                        </h2>
                        <span className="text-xs text-amber-700/80 font-devanagari block mt-1">
                          भजन क्रमांक {activeBhajan.bhajan_number} | पाण्डुलिपि पृष्ठ {activeBhajan.original_page_number}
                        </span>
                      </div>

                      {/* Bhajan Text */}
                      <div
                        className={`whitespace-pre-wrap text-stone-800 ${getFontFamilyClass()} tracking-wide transition-all`}
                        style={{
                          fontSize: `${fontSize}px`,
                          lineHeight: lineHeight
                        }}
                      >
                        {activeBhajan.text}
                      </div>

                      {/* Devotional Colophon Accent */}
                      <div className="mt-10 pt-4 border-t border-amber-200/40 text-center">
                        <span className="text-amber-700/70 font-devanagari text-xs">
                          ॥ इति शुभम् ॥
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Reading Footer: Next / Prev Navigation */}
                  <div className="p-3 sm:p-4 border-t border-stone-100 bg-[#fdfbf7] flex items-center justify-between gap-3">
                    <button
                      type="button"
                      onClick={handlePrevBhajan}
                      disabled={activeIndex <= 0}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl border border-stone-200 hover:bg-stone-50 disabled:opacity-40 disabled:pointer-events-none text-stone-700 text-xs font-bold font-devanagari transition-colors"
                    >
                      <ChevronLeft className="w-4 h-4" />
                      <span>{isHi ? 'पिछला भजन' : 'Previous Bhajan'}</span>
                    </button>

                    <span className="text-xs text-stone-500 font-devanagari">
                      {activeIndex + 1} / {filteredBhajans.length}
                    </span>

                    <button
                      type="button"
                      onClick={handleNextBhajan}
                      disabled={activeIndex < 0 || activeIndex >= filteredBhajans.length - 1}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-vedic-700 hover:bg-vedic-800 disabled:opacity-40 disabled:pointer-events-none text-white text-xs font-bold font-devanagari transition-colors shadow-2xs"
                    >
                      <span>{isHi ? 'अगला भजन' : 'Next Bhajan'}</span>
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </>
              ) : (
                <div className="p-12 text-center text-stone-400 font-devanagari text-sm">
                  {isHi ? 'सूची से कोई भजन चुनें।' : 'Select a bhajan to view.'}
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Side Drawer: High-Resolution Original Manuscript Page Viewer */}
      {isScanDrawerOpen && activeBhajan && (
        <div className="fixed inset-0 z-50 overflow-hidden flex justify-end">
          {/* Backdrop */}
          <div
            onClick={() => setIsScanDrawerOpen(false)}
            className="fixed inset-0 bg-stone-900/60 backdrop-blur-xs transition-opacity"
          />

          {/* Drawer Panel */}
          <div className="relative w-full max-w-2xl bg-stone-900 text-stone-100 shadow-2xl flex flex-col h-full z-10 animate-in slide-in-from-right duration-200">
            {/* Drawer Header */}
            <div className="p-4 border-b border-stone-800 flex items-center justify-between gap-3 bg-stone-950/80">
              <div className="flex items-center gap-2 min-w-0">
                <ImageIcon className="w-5 h-5 text-amber-500 shrink-0" />
                <div className="min-w-0">
                  <h3 className="text-sm font-bold font-devanagari truncate text-amber-200">
                    मूल हस्तलिखित पाण्डुलिपि — पृष्ठ {activeBhajan.original_page_number}
                  </h3>
                  <span className="text-[11px] text-stone-400 font-devanagari block truncate">
                    भजन क्रमांक {activeBhajan.bhajan_number}: {activeBhajan.title === 'unknown' ? 'अज्ञात शीर्षक' : activeBhajan.title}
                  </span>
                </div>
              </div>

              {/* Drawer Controls */}
              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  type="button"
                  onClick={() => setImageZoom(z => Math.max(0.6, z - 0.2))}
                  className="p-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-300"
                  title="Zoom Out"
                >
                  <ZoomOut className="w-4 h-4" />
                </button>
                <span className="text-[11px] font-mono text-stone-400 px-1">{Math.round(imageZoom * 100)}%</span>
                <button
                  type="button"
                  onClick={() => setImageZoom(z => Math.min(3.0, z + 0.2))}
                  className="p-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-300"
                  title="Zoom In"
                >
                  <ZoomIn className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setImageZoom(1);
                    setImageRotation(0);
                  }}
                  className="p-1.5 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-300"
                  title="Reset View"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setIsScanDrawerOpen(false)}
                  className="p-1.5 rounded-lg bg-stone-800 hover:bg-rose-900/60 text-stone-300 hover:text-white ml-2 transition-colors"
                  title="Close"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Drawer Image Display Container */}
            <div className="flex-1 overflow-auto p-4 flex items-center justify-center bg-stone-950 select-none">
              {activeBhajan.page_image_url ? (
                <div
                  className="transition-transform duration-150 origin-center"
                  style={{
                    transform: `scale(${imageZoom}) rotate(${imageRotation}deg)`
                  }}
                >
                  <img
                    src={getStorageUrl(activeBhajan.page_image_url)}
                    alt={`Manuscript page ${activeBhajan.original_page_number}`}
                    className="max-h-[82vh] w-auto object-contain rounded-lg shadow-2xl border border-stone-800"
                    onError={(e) => {
                      e.currentTarget.style.display = 'none';
                    }}
                  />
                </div>
              ) : (
                <div className="text-center text-stone-500 font-devanagari text-xs">
                  {isHi ? 'इस पृष्ठ की मूल छवि संचिका उपलब्ध नहीं है।' : 'Original manuscript image not available for this page.'}
                </div>
              )}
            </div>

            {/* Drawer Footer Information */}
            <div className="p-3 border-t border-stone-800 bg-stone-950/90 text-stone-400 text-xs font-devanagari flex items-center justify-between">
              <span>
                💡 स्कैन को जूम एवं स्पष्ट अवलोकन कर पाठ का मिलान करें।
              </span>
              <button
                type="button"
                onClick={() => setIsScanDrawerOpen(false)}
                className="px-3 py-1 rounded-lg bg-stone-800 hover:bg-stone-700 text-stone-200 text-xs font-bold font-devanagari"
              >
                {isHi ? 'बन्द करें' : 'Close'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
