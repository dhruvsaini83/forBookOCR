import React, { useState, useEffect } from 'react';
import {
  FileText, Download, Code, Printer, FileDown,
  CheckCircle2, AlertCircle, Copy, Check, ExternalLink,
  ArrowLeft, Home, Layers, Sparkles, RefreshCw,
  Sliders, ShieldCheck, CheckSquare, Square,
  FileCode, Globe, BookOpen
} from 'lucide-react';
import { api, BACKEND_URL } from '../services/api';
import { copyToClipboard } from '../utils/clipboard';
import type { ExportFormat, ExportScope, BookExportResponse, BookData } from '../types';
import type { Language } from '../i18n/translations';

interface BookExportProps {
  bookId?: string;
  lang?: Language;
  onNavigateBack?: () => void;
  onNavigateHome?: () => void;
  onOpenBookBuilder?: (bookId: string) => void;
  onOpenLibrary?: (bookId: string) => void;
}

export const BookExport: React.FC<BookExportProps> = ({
  bookId: propBookId,
  lang = 'hi',
  onNavigateBack,
  onNavigateHome,
  onOpenBookBuilder,
  onOpenLibrary
}) => {
  const isHi = lang === 'hi';

  // Books State
  const [books, setBooks] = useState<BookData[]>([]);
  const [selectedBookId, setSelectedBookId] = useState<string>(propBookId || '');
  const [currentBook, setCurrentBook] = useState<BookData | null>(null);

  // Export Form State
  const [selectedFormat, setSelectedFormat] = useState<ExportFormat>('pdf');
  const [scope, setScope] = useState<ExportScope>('complete');
  const [selectedPagesInput, setSelectedPagesInput] = useState<string>('');
  const [includePageNumbers, setIncludePageNumbers] = useState<boolean>(true);
  const [includePageBreaks, setIncludePageBreaks] = useState<boolean>(true);
  const [onlyVerified, setOnlyVerified] = useState<boolean>(false);

  // Status & Response State
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [exportResult, setExportResult] = useState<BookExportResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copiedUrl, setCopiedUrl] = useState<boolean>(false);

  // 1. Initial Load: Books
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

  // 2. Fetch active book details
  useEffect(() => {
    if (!selectedBookId) return;
    const fetchBookDetails = async () => {
      try {
        const res = await api.getBook(selectedBookId);
        if (res && res.book) {
          setCurrentBook(res.book);
        }
      } catch (err) {
        console.error('Failed to fetch book:', err);
      }
    };
    fetchBookDetails();
    setExportResult(null);
    setErrorMsg(null);
  }, [selectedBookId]);

  // Format definitions
  const formatCards: Array<{
    id: ExportFormat;
    titleHi: string;
    titleEn: string;
    subHi: string;
    subEn: string;
    ext: string;
    badge: string;
    icon: React.ReactNode;
    cardBorder: string;
    cardBg: string;
  }> = [
    {
      id: 'pdf',
      titleHi: 'मुद्रण योग्य PDF',
      titleEn: 'Print-Ready PDF',
      subHi: 'ReportLab NotoSansDevanagari वेक्टर फॉन्ट (अटूट देवनागरी)। मुद्रण व वाचन हेतु सर्वोत्कृष्ट।',
      subEn: 'Vector NotoSansDevanagari TrueType font with zero broken glyphs. Ideal for printing.',
      ext: '.pdf',
      badge: 'वेक्टर मुद्रण',
      icon: <FileDown className="w-6 h-6 text-rose-600" />,
      cardBorder: 'hover:border-rose-400',
      cardBg: 'bg-rose-50/20'
    },
    {
      id: 'docx',
      titleHi: 'वर्ड दस्तावेज़',
      titleEn: 'Microsoft Word',
      subHi: 'Noto Sans Devanagari फॉन्ट स्टैक, केन्द्रित छंद/दोहा संरेखण, पृष्ठ क्रमांक व पृष्ठ ब्रेक।',
      subEn: 'Noto Sans Devanagari font with centered verse couplets and page breaks.',
      ext: '.docx',
      badge: 'छंद संरेखण',
      icon: <FileText className="w-6 h-6 text-blue-600" />,
      cardBorder: 'hover:border-blue-400',
      cardBg: 'bg-blue-50/20'
    },
    {
      id: 'txt',
      titleHi: 'स्वच्छ पाठ',
      titleEn: 'Clean Text',
      subHi: 'हल्की एवं सरल देवनागरी पाठ संचिका (UTF-8)। सभी मोबाइल व कम्प्यूटर में तुरंत पढ़ने योग्य।',
      subEn: 'Clean UTF-8 plain text file preserving stanza breaks and page numbers.',
      ext: '.txt',
      badge: 'UTF-8 सरल',
      icon: <BookOpen className="w-6 h-6 text-emerald-600" />,
      cardBorder: 'hover:border-emerald-400',
      cardBg: 'bg-emerald-50/20'
    },
    {
      id: 'json',
      titleHi: 'संरचित डेटा',
      titleEn: 'Structured JSON',
      subHi: 'शोधार्थियों हेतु प्रत्येक पृष्ठ के शब्द, Bounding Box निर्देशांक (bbox) व विश्वास स्तर (Confidence)।',
      subEn: 'Machine-readable structured JSON with word tokens, bounding boxes, and confidence.',
      ext: '.json',
      badge: 'BBox + OCR',
      icon: <Code className="w-6 h-6 text-purple-600" />,
      cardBorder: 'hover:border-purple-400',
      cardBg: 'bg-purple-50/20'
    },
    {
      id: 'html',
      titleHi: 'वेब संस्करण',
      titleEn: 'Printable HTML',
      subHi: 'Google Fonts एवं प्रिंट-रेडी CSS सहित सुंदर वेब दस्तावेज़। सीधे ब्राउज़र में देखें या प्रिंट करें।',
      subEn: 'Self-contained HTML document with embedded CSS, Google Fonts, and print media rules.',
      ext: '.html',
      badge: 'वेब मुद्रण',
      icon: <Globe className="w-6 h-6 text-amber-600" />,
      cardBorder: 'hover:border-amber-400',
      cardBg: 'bg-amber-50/20'
    },
    {
      id: 'md',
      titleHi: 'मार्कडाउन',
      titleEn: 'Markdown',
      subHi: 'GitHub, Obsidian, Logseq व Notion में सीधे उपयोग योग्य सुसंगत मार्कडाउन (.md) स्वरूप।',
      subEn: 'Universal Markdown document formatted for digital note-taking and documentation.',
      ext: '.md',
      badge: 'Obsidian / Git',
      icon: <FileCode className="w-6 h-6 text-teal-600" />,
      cardBorder: 'hover:border-teal-400',
      cardBg: 'bg-teal-50/20'
    }
  ];

  // Handle Export Action
  const handleGenerateExport = async () => {
    if (!selectedBookId) return;

    try {
      setIsExporting(true);
      setErrorMsg(null);
      setExportResult(null);

      const res = await api.exportBook(
        selectedBookId,
        selectedFormat,
        scope,
        scope === 'selected' ? selectedPagesInput.trim() : undefined,
        {
          include_page_numbers: includePageNumbers,
          include_page_breaks: includePageBreaks,
          only_verified: onlyVerified
        }
      );

      setExportResult(res);
    } catch (err: any) {
      console.error('Export failed:', err);
      setErrorMsg(err.message || (isHi ? 'निर्यात संचिका तैयार करने में त्रुटि हुई।' : 'Export generation failed.'));
    } finally {
      setIsExporting(false);
    }
  };

  // Handle Direct Download
  const handleDirectDownload = () => {
    if (!selectedBookId) return;
    const url = api.getBookExportDirectUrl(
      selectedBookId,
      selectedFormat,
      scope,
      scope === 'selected' ? selectedPagesInput.trim() : undefined,
      {
        include_page_numbers: includePageNumbers,
        include_page_breaks: includePageBreaks,
        only_verified: onlyVerified
      }
    );
    window.open(url, '_blank');
  };

  // Copy Presigned URL
  const handleCopyPresignedUrl = async (url: string) => {
    try {
      const fullUrl = url.startsWith('http') ? url : `${BACKEND_URL}${url}`;
      await copyToClipboard(fullUrl);
      setCopiedUrl(true);
      setTimeout(() => setCopiedUrl(false), 2000);
    } catch (err) {
      console.error('Failed to copy URL:', err);
    }
  };

  // Format file size
  const formatBytes = (bytes: number) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  return (
    <div className="min-h-screen bg-[#faf8f5] flex flex-col text-stone-900 font-sans">
      {/* Top Header */}
      <header className="sticky top-0 z-20 bg-white/95 backdrop-blur-md border-b border-stone-200/90 shadow-2xs">
        <div className="max-w-7xl w-full mx-auto px-3 sm:px-6 lg:px-8 h-16 sm:h-18 flex items-center justify-between gap-3">
          {/* Back & Title */}
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
              <Download className="w-5 h-5" />
            </div>

            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-base sm:text-lg font-bold font-devanagari text-vedic-950 truncate">
                  {isHi ? 'ग्रन्थ निर्यात एवं डिजिटल संरक्षण' : 'Book Export & Preservation'}
                </h1>
                <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-300 shrink-0">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                  <span>R2 Cloud Storage</span>
                </span>
              </div>
              <p className="text-[11px] text-stone-500 font-devanagari truncate">
                {currentBook?.name ? `${currentBook.name} — ` : ''}
                {isHi ? '६ विभिन्न प्रारूपों (DOCX, PDF, TXT, JSON, HTML, MD) में उच्च-गुणवत्ता निर्यात' : 'Export in 6 high-quality formats with Devanagari typography'}
              </p>
            </div>
          </div>

          {/* Book Switcher & Shortcuts */}
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

            {onOpenLibrary && selectedBookId && (
              <button
                type="button"
                onClick={() => onOpenLibrary(selectedBookId)}
                className="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-vedic-50 hover:bg-vedic-100 text-vedic-800 border border-vedic-300 font-bold text-xs font-devanagari transition-colors shadow-2xs"
                title={isHi ? 'पुस्तकालय देखें' : 'Open Library'}
              >
                <BookOpen className="w-3.5 h-3.5 text-vedic-700" />
                <span>{isHi ? 'पुस्तकालय' : 'Library'}</span>
              </button>
            )}

            {onOpenBookBuilder && selectedBookId && (
              <button
                type="button"
                onClick={() => onOpenBookBuilder(selectedBookId)}
                className="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-300 font-bold text-xs font-devanagari transition-colors shadow-2xs"
                title={isHi ? 'पुस्तक संकलक में जाएँ' : 'Open Book Builder'}
              >
                <Layers className="w-3.5 h-3.5 text-vedic-700" />
                <span>{isHi ? 'संकलक' : 'Builder'}</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-3 sm:px-6 lg:px-8 py-6 sm:py-8 flex flex-col gap-6 sm:gap-8">
        {/* Error Notification */}
        {errorMsg && (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-devanagari flex items-center justify-between shadow-2xs">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{errorMsg}</span>
            </div>
            <button type="button" onClick={() => setErrorMsg(null)} className="text-rose-500 hover:text-rose-800">
              <span className="sr-only">Close</span>
              &times;
            </button>
          </div>
        )}

        {/* Section 1: Format Selection Cards (6 Cards) */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-base sm:text-lg font-bold font-devanagari text-vedic-950 flex items-center gap-2">
                <span>१. निर्यात प्रारूप चुनें (Select Export Format)</span>
              </h2>
              <p className="text-xs text-stone-500 font-devanagari">
                {isHi ? 'अपनी आवश्यकतानुसार उपयुक्त संचिका प्रारूप का चयन करें:' : 'Choose the best output format for your workflow:'}
              </p>
            </div>
            <span className="text-xs font-bold font-mono text-vedic-700 bg-vedic-50 border border-vedic-200 px-2 py-0.5 rounded-md">
              .{selectedFormat.toUpperCase()}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {formatCards.map((card) => {
              const isSelected = selectedFormat === card.id;

              return (
                <div
                  key={card.id}
                  onClick={() => setSelectedFormat(card.id)}
                  className={`p-4 rounded-2xl border-2 cursor-pointer transition-all flex flex-col justify-between relative overflow-hidden select-none ${
                    isSelected
                      ? 'border-vedic-700 bg-white shadow-md ring-2 ring-vedic-500/20'
                      : `border-stone-200/90 bg-white hover:bg-stone-50/60 shadow-2xs ${card.cardBorder}`
                  }`}
                >
                  {/* Top Bar: Icon & Badge */}
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="p-2 rounded-xl bg-stone-50 border border-stone-100 shadow-2xs shrink-0">
                      {card.icon}
                    </div>

                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] font-bold font-devanagari bg-stone-100 text-stone-700 px-2 py-0.5 rounded-md border border-stone-200">
                        {card.badge}
                      </span>
                      <div className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                        isSelected ? 'border-vedic-700 bg-vedic-700 text-white' : 'border-stone-300'
                      }`}>
                        {isSelected && <Check className="w-2.5 h-2.5 stroke-3" />}
                      </div>
                    </div>
                  </div>

                  {/* Card Title & Desc */}
                  <div>
                    <h3 className="font-devanagari font-bold text-sm text-stone-900 mb-1 flex items-center gap-1.5">
                      <span>{isHi ? card.titleHi : card.titleEn}</span>
                      <span className="font-mono text-xs font-semibold text-stone-400">({card.ext})</span>
                    </h3>
                    <p className="font-devanagari text-xs text-stone-500 leading-relaxed">
                      {isHi ? card.subHi : card.subEn}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Section 2: Options Checkboxes & Scope */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 items-start">
          {/* Left: Options Checkboxes */}
          <div className="bg-white rounded-2xl border border-stone-200/90 p-5 shadow-2xs">
            <h3 className="text-sm font-bold font-devanagari text-vedic-950 mb-3 flex items-center gap-2">
              <Sliders className="w-4 h-4 text-vedic-700" />
              <span>२. प्रारूप विकल्प (Formatting Options)</span>
            </h3>

            <div className="space-y-3.5">
              {/* Option 1: Include Page Numbers */}
              <label className="flex items-start gap-3 cursor-pointer group">
                <button
                  type="button"
                  onClick={() => setIncludePageNumbers(!includePageNumbers)}
                  className="mt-0.5 text-vedic-700 focus:outline-hidden"
                >
                  {includePageNumbers ? (
                    <CheckSquare className="w-5 h-5 text-vedic-700 fill-vedic-50" />
                  ) : (
                    <Square className="w-5 h-5 text-stone-400 group-hover:text-stone-600" />
                  )}
                </button>
                <div className="text-xs font-devanagari select-none">
                  <span className="font-bold text-stone-900 block">
                    {isHi ? 'पृष्ठ संख्या व हेडर शामिल करें' : 'Include Page Numbers & Headers'}
                  </span>
                  <span className="text-stone-500">
                    {isHi ? 'प्रत्येक पृष्ठ के शीर्ष पर "॥ पृष्ठ क्रमांक ॥" हेडर जोड़ता है।' : 'Adds page number header at top of each section.'}
                  </span>
                </div>
              </label>

              {/* Option 2: Include Page Breaks */}
              <label className="flex items-start gap-3 cursor-pointer group">
                <button
                  type="button"
                  onClick={() => setIncludePageBreaks(!includePageBreaks)}
                  className="mt-0.5 text-vedic-700 focus:outline-hidden"
                >
                  {includePageBreaks ? (
                    <CheckSquare className="w-5 h-5 text-vedic-700 fill-vedic-50" />
                  ) : (
                    <Square className="w-5 h-5 text-stone-400 group-hover:text-stone-600" />
                  )}
                </button>
                <div className="text-xs font-devanagari select-none">
                  <span className="font-bold text-stone-900 block">
                    {isHi ? 'पृष्ठ अंतराल / पेज ब्रेक दें (Page Breaks)' : 'Include Page Breaks'}
                  </span>
                  <span className="text-stone-500">
                    {isHi ? 'DOCX, PDF एवं HTML में हर पृष्ठ को नए पेज पर आरंभ करता है (मुद्रण अनुकूल)।' : 'Starts each page on a new sheet for DOCX, PDF, and HTML print.'}
                  </span>
                </div>
              </label>

              {/* Option 3: Only Verified Pages */}
              <label className="flex items-start gap-3 cursor-pointer group">
                <button
                  type="button"
                  onClick={() => setOnlyVerified(!onlyVerified)}
                  className="mt-0.5 text-vedic-700 focus:outline-hidden"
                >
                  {onlyVerified ? (
                    <CheckSquare className="w-5 h-5 text-vedic-700 fill-vedic-50" />
                  ) : (
                    <Square className="w-5 h-5 text-stone-400 group-hover:text-stone-600" />
                  )}
                </button>
                <div className="text-xs font-devanagari select-none">
                  <span className="font-bold text-stone-900 block flex items-center gap-1.5">
                    <span>{isHi ? 'केवल सत्यापित पृष्ठ ही निर्यात करें' : 'Only Verified Pages'}</span>
                    <span className="text-[10px] bg-emerald-100 text-emerald-800 px-1.5 py-0.2 rounded font-semibold">
                      Verified
                    </span>
                  </span>
                  <span className="text-stone-500">
                    {isHi ? 'प्रक्रियाधीन या असत्यापित पृष्ठों को छोड़कर केवल ५-चरणीय पुष्ट पृष्ठ लेता है।' : 'Excludes pending/unverified pages from the export.'}
                  </span>
                </div>
              </label>
            </div>
          </div>

          {/* Right: Scope Selection */}
          <div className="bg-white rounded-2xl border border-stone-200/90 p-5 shadow-2xs">
            <h3 className="text-sm font-bold font-devanagari text-vedic-950 mb-3 flex items-center gap-2">
              <Printer className="w-4 h-4 text-vedic-700" />
              <span>३. निर्यात का दायरा (Export Scope)</span>
            </h3>

            <div className="space-y-4">
              {/* Radio: Complete Book */}
              <label className="flex items-center gap-3 cursor-pointer p-2.5 rounded-xl border border-stone-200 hover:bg-stone-50 transition-colors">
                <input
                  type="radio"
                  name="export_scope"
                  checked={scope === 'complete'}
                  onChange={() => setScope('complete')}
                  className="text-vedic-700 focus:ring-vedic-500 h-4 w-4"
                />
                <div className="text-xs font-devanagari">
                  <span className="font-bold text-stone-900 block">
                    {isHi ? 'संपूर्ण ग्रन्थ (Complete Book)' : 'Complete Book'}
                  </span>
                  <span className="text-stone-500">
                    {currentBook ? `${currentBook.total_pages || 0} पृष्ठों का समग्र संग्रह` : 'All pages of this book'}
                  </span>
                </div>
              </label>

              {/* Radio: Selected Pages */}
              <div className="p-2.5 rounded-xl border border-stone-200 hover:bg-stone-50 transition-colors">
                <label className="flex items-center gap-3 cursor-pointer mb-2">
                  <input
                    type="radio"
                    name="export_scope"
                    checked={scope === 'selected'}
                    onChange={() => setScope('selected')}
                    className="text-vedic-700 focus:ring-vedic-500 h-4 w-4"
                  />
                  <div className="text-xs font-devanagari">
                    <span className="font-bold text-stone-900 block">
                      {isHi ? 'चयनित विशिष्ट पृष्ठ (Selected Pages)' : 'Selected Pages Only'}
                    </span>
                    <span className="text-stone-500">
                      {isHi ? 'केवल चयनित पृष्ठ संख्या या ID' : 'Specific page numbers or IDs'}
                    </span>
                  </div>
                </label>

                {scope === 'selected' && (
                  <div className="pl-7 mt-2">
                    <input
                      type="text"
                      value={selectedPagesInput}
                      onChange={(e) => setSelectedPagesInput(e.target.value)}
                      placeholder={isHi ? 'उदा: 1, 2, 5 (अल्पविराम से अलग)' : 'e.g. 1, 2, 5 (comma-separated)'}
                      className="w-full text-xs font-devanagari px-3 py-2 rounded-lg border border-stone-300 focus:ring-2 focus:ring-vedic-500 focus:outline-hidden bg-white"
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Section 3: Action Buttons & Generation */}
        <div className="bg-white rounded-2xl border border-stone-200/90 p-5 shadow-2xs flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="text-xs font-devanagari text-stone-600">
            <span className="font-bold text-stone-900 block mb-0.5">
              प्रारूप: <span className="text-vedic-800 uppercase font-mono">.{selectedFormat}</span> | दायरा: <span className="font-semibold">{scope === 'complete' ? 'संपूर्ण पुस्तक' : 'चयनित पृष्ठ'}</span>
            </span>
            <span className="text-stone-500">
              संचिका Cloudflare R2 क्लाउड स्टोरेज में <code>exports/{selectedBookId || 'book'}/</code> के अंतर्गत सुरक्षित होगी।
            </span>
          </div>

          <div className="flex items-center gap-2.5 w-full sm:w-auto">
            <button
              type="button"
              onClick={handleDirectDownload}
              disabled={isExporting}
              className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-stone-300 hover:bg-stone-100 text-stone-700 text-xs font-bold font-devanagari transition-colors shadow-2xs"
              title={isHi ? 'ब्राउज़र से सीधा डाउनलोड करें' : 'Direct browser download'}
            >
              <Download className="w-4 h-4 text-stone-600" />
              <span>{isHi ? 'सीधा डाउनलोड' : 'Direct Download'}</span>
            </button>

            <button
              type="button"
              onClick={handleGenerateExport}
              disabled={isExporting}
              className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-vedic-700 hover:bg-vedic-800 disabled:opacity-50 text-white text-xs font-bold font-devanagari transition-colors shadow-md"
            >
              {isExporting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin text-white" />
                  <span>{isHi ? 'संचिका तैयार हो रही है...' : 'Generating & Uploading...'}</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-amber-300" />
                  <span>{isHi ? 'R2 पर निर्यात करें (Export)' : 'Generate & Save to R2'}</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Section 4: Export Result Card (Presigned URL & Download Info) */}
        {exportResult && (
          <div className="bg-emerald-50/70 rounded-2xl border border-emerald-300 p-5 shadow-xs flex flex-col gap-4 animate-in fade-in duration-200">
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-emerald-600 text-white flex items-center justify-center shadow-2xs shrink-0">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="font-devanagari font-bold text-sm text-emerald-950">
                    {isHi ? 'निर्यात संचिका सफलतापूर्वक तैयार एवं सुरक्षित हो गई!' : 'Export File Successfully Generated!'}
                  </h3>
                  <p className="text-xs text-emerald-800 font-devanagari">
                    संचिका नाम: <code className="font-mono bg-white/70 px-1.5 py-0.5 rounded border border-emerald-200 text-emerald-900">{exportResult.filename}</code> | आकार: {formatBytes(exportResult.file_size)} | पृष्ठ संख्या: {exportResult.pages_count}
                  </p>
                </div>
              </div>

              {/* Download Buttons */}
              <div className="flex items-center gap-2 ml-auto">
                <a
                  href={exportResult.presigned_url}
                  download={exportResult.filename}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-xs font-devanagari transition-colors shadow-2xs"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>{isHi ? 'डाउनलोड करें' : 'Download Now'}</span>
                </a>

                <a
                  href={exportResult.presigned_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2 rounded-xl border border-emerald-300 bg-white hover:bg-emerald-50 text-emerald-800 transition-colors"
                  title={isHi ? 'नई विंडो में खोलें' : 'Open in new tab'}
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
              </div>
            </div>

            {/* Presigned URL Display Box */}
            <div className="bg-white rounded-xl border border-emerald-200 p-3 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5">
              <div className="min-w-0 flex-1">
                <span className="text-[10px] font-bold uppercase text-emerald-800 tracking-wider block font-devanagari mb-0.5">
                  Cloudflare R2 Presigned Download URL (24 घंटे वैध):
                </span>
                <p className="font-mono text-xs text-stone-600 truncate select-all">
                  {exportResult.presigned_url}
                </p>
              </div>

              <button
                type="button"
                onClick={() => handleCopyPresignedUrl(exportResult.presigned_url)}
                className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg border border-stone-200 hover:bg-stone-50 text-stone-700 text-xs font-devanagari font-semibold shrink-0"
              >
                {copiedUrl ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="text-emerald-700 font-bold">{isHi ? 'कॉपी हुआ!' : 'Copied!'}</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5 text-stone-600" />
                    <span>{isHi ? 'URL कॉपी करें' : 'Copy URL'}</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

