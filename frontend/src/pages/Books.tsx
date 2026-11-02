import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  BookOpen, Plus, Search, Edit3, Trash2, CheckCircle2,
  Clock, AlertTriangle, X, Image as ImageIcon, UploadCloud,
  ArrowLeft, RefreshCw, ShieldCheck, Sparkles, Layers, ArrowUpDown, BookMarked, Download, BrainCircuit
} from 'lucide-react';
import { api, getStorageUrl } from '../services/api';
import type { BookData, BookStatus, CreateBookPayload, UpdateBookPayload, DashboardMetrics } from '../types';
import type { Language } from '../i18n/translations';
import { BookPageReorderModal } from '../components/BookPageReorderModal';

interface BooksProps {
  lang?: Language;
  onNavigateHome?: () => void;
  onSelectBook?: (bookId: string) => void;
  onOpenBookBuilder?: (bookId: string) => void;
  onOpenLibrary?: (bookId: string) => void;
  onOpenExport?: (bookId: string) => void;
  onOpenLearning?: (bookId: string) => void;
  onOpenVerify?: (bookId: string) => void;
}

export const Books: React.FC<BooksProps> = ({
  lang = 'hi',
  onNavigateHome,
  onSelectBook,
  onOpenBookBuilder,
  onOpenLibrary,
  onOpenExport,
  onOpenLearning,
  onOpenVerify
}) => {
  const isHi = lang === 'hi';

  // State
  const [books, setBooks] = useState<BookData[]>([]);
  const [metrics, setMetrics] = useState<DashboardMetrics>({
    total: 0,
    uploaded: 0,
    ocr_done: 0,
    verified: 0,
    added_to_book: 0
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Modals & Forms
  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [isEditOpen, setIsEditOpen] = useState<boolean>(false);
  const [bookToEdit, setBookToEdit] = useState<BookData | null>(null);
  const [bookToDelete, setBookToDelete] = useState<BookData | null>(null);
  const [bookForReorder, setBookForReorder] = useState<BookData | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Form State
  const [formName, setFormName] = useState<string>('');
  const [formDescription, setFormDescription] = useState<string>('');
  const [formLanguage, setFormLanguage] = useState<string>('hin');
  const [formTotalPages, setFormTotalPages] = useState<number>(400);
  const [formCoverUrl, setFormCoverUrl] = useState<string>('');

  const [formCoverPreview, setFormCoverPreview] = useState<string>('');
  const [formStatus, setFormStatus] = useState<BookStatus>('draft');
  const [formError, setFormError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch Books and Metrics
  const loadBooksData = async () => {
    try {
      setIsLoading(true);
      setErrorMsg(null);
      const res = await api.listBooks();
      if (res && res.books) {
        setBooks(res.books);
        if (res.dashboard_metrics) {
          setMetrics(res.dashboard_metrics);
        }
      }
    } catch (err: any) {
      console.error('Failed to load books:', err);
      setErrorMsg(err.message || (isHi ? 'ग्रन्थ सूची लोड करने में त्रुटि हुई।' : 'Failed to load books.'));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadBooksData();
  }, []);

  // Handle Cover File Selection
  const handleCoverFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      setFormError(isHi ? 'कृपया केवल छवि (JPG, PNG, WEBP) संचिका चुनें।' : 'Please select a valid image file.');
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      setFormCoverPreview(reader.result as string);
      setFormCoverUrl(reader.result as string);
    };
    reader.readAsDataURL(file);
    setFormError(null);
  };

  // Open Create Modal
  const handleOpenCreate = () => {
    setFormName('');
    setFormDescription('');
    setFormLanguage('hin');
    setFormTotalPages(400);
    setFormCoverUrl('');

    setFormCoverPreview('');
    setFormStatus('draft');
    setFormError(null);
    setIsCreateOpen(true);
  };

  // Open Edit Modal
  const handleOpenEdit = (book: BookData) => {
    setBookToEdit(book);
    setFormName(book.name);
    setFormDescription(book.description || '');
    setFormLanguage(book.language || 'hin');
    setFormTotalPages(book.total_pages || 400);
    setFormCoverUrl(book.cover_image_url || '');
    setFormCoverPreview(book.cover_image_url ? getStorageUrl(book.cover_image_url) : '');

    setFormStatus(book.status);
    setFormError(null);
    setIsEditOpen(true);
  };

  // Submit Create Book
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formName.trim()) {
      setFormError(isHi ? 'ग्रन्थ का नाम अनिवार्य है।' : 'Book title is required.');
      return;
    }
    if (formTotalPages <= 0) {
      setFormError(isHi ? 'पृष्ठों की संख्या 0 से अधिक होनी चाहिए।' : 'Total pages must be greater than 0.');
      return;
    }

    try {
      setIsSubmitting(true);
      setFormError(null);
      const payload: CreateBookPayload = {
        name: formName.trim(),
        description: formDescription.trim() || undefined,
        language: formLanguage,
        total_pages: Number(formTotalPages),
        cover_image_url: formCoverUrl || undefined
      };
      await api.createBook(payload);
      setIsCreateOpen(false);
      await loadBooksData();
    } catch (err: any) {
      setFormError(err.message || (isHi ? 'ग्रन्थ सुरक्षित करने में त्रुटि हुई।' : 'Failed to create book.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  // Submit Edit Book
  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bookToEdit) return;
    if (!formName.trim()) {
      setFormError(isHi ? 'ग्रन्थ का नाम अनिवार्य है।' : 'Book title is required.');
      return;
    }

    try {
      setIsSubmitting(true);
      setFormError(null);
      const payload: UpdateBookPayload = {
        name: formName.trim(),
        description: formDescription.trim() || undefined,
        language: formLanguage,
        total_pages: Number(formTotalPages),
        cover_image_url: formCoverUrl || undefined,
        status: formStatus
      };
      await api.updateBook(bookToEdit.id, payload);
      setIsEditOpen(false);
      setBookToEdit(null);
      await loadBooksData();
    } catch (err: any) {
      setFormError(err.message || (isHi ? 'ग्रन्थ अद्यतन करने में त्रुटि हुई।' : 'Failed to update book.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  // Execute Delete
  const handleDeleteConfirm = async () => {
    if (!bookToDelete) return;
    try {
      setIsSubmitting(true);
      await api.deleteBook(bookToDelete.id, true);
      setBookToDelete(null);
      await loadBooksData();
    } catch (err: any) {
      alert(err.message || (isHi ? 'ग्रन्थ हटाने में त्रुटि हुई।' : 'Failed to delete book.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  // Navigate to /books/{id}
  const handleNavigateToBook = (bookId: string) => {
    const targetUrl = `/books/${bookId}`;
    if (typeof window !== 'undefined') {
      window.history.pushState({ bookId }, '', targetUrl);
      window.dispatchEvent(new CustomEvent('app:navigate', { detail: { path: targetUrl, bookId } }));
    }
    if (onSelectBook) {
      onSelectBook(bookId);
    }
  };

  // Filtered Books
  const filteredBooks = useMemo(() => {
    return books.filter((b) => {
      const matchSearch =
        searchQuery.trim() === '' ||
        b.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (b.description && b.description.toLowerCase().includes(searchQuery.toLowerCase()));

      const matchStatus =
        statusFilter === 'all' || b.status === statusFilter;

      return matchSearch && matchStatus;
    });
  }, [books, searchQuery, statusFilter]);

  return (
    <div className="min-h-screen bg-stone-50/60 pb-20 font-sans text-stone-900 selection:bg-vedic-100 selection:text-vedic-900">
      {/* Top Breadcrumb & Actions Bar */}
      <div className="bg-white border-b border-stone-200/90 shadow-2xs sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            {onNavigateHome && (
              <button
                type="button"
                onClick={onNavigateHome}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-stone-600 hover:text-vedic-950 hover:bg-stone-100 font-devanagari text-xs font-semibold transition-colors shrink-0"
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="hidden sm:inline">{isHi ? 'मुख्य कार्यक्षेत्र' : 'Back to OCR'}</span>
              </button>
            )}
            <div className="h-5 w-px bg-stone-200 hidden sm:block" />
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-vedic-700 text-white flex items-center justify-center font-traditional font-bold shrink-0 shadow-2xs">
                ग्र
              </div>
              <h1 className="text-base sm:text-xl font-bold font-devanagari text-vedic-950 truncate">
                {isHi ? 'ग्रन्थ संग्रह एवं पाण्डुलिपि पुस्तकालय' : 'Heritage Books Library'}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={handleOpenCreate}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-vedic-700 hover:bg-vedic-800 active:bg-vedic-900 text-white font-bold text-xs sm:text-sm font-devanagari shadow-xs transition-all hover:shadow-sm"
            >
              <Plus className="w-4 h-4" />
              <span>{isHi ? 'नया ग्रन्थ जोड़ें' : 'New Book'}</span>
            </button>
          </div>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 sm:pt-8 space-y-6">
        {/* Dashboard Overview Metrics Ribbon */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 sm:gap-4">
          <div className="bg-white p-4 rounded-2xl border border-stone-200/90 shadow-2xs flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-vedic-50 text-vedic-700 flex items-center justify-center shrink-0 border border-vedic-200">
              <BookOpen className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-semibold text-stone-500 font-devanagari truncate">
                {isHi ? 'कुल ग्रन्थ' : 'Total Books'}
              </p>
              <p className="text-xl font-bold text-vedic-950 font-sans tracking-tight">
                {metrics.total}
              </p>
            </div>
          </div>

          <div className="bg-white p-4 rounded-2xl border border-stone-200/90 shadow-2xs flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-700 flex items-center justify-center shrink-0 border border-blue-200">
              <UploadCloud className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-semibold text-stone-500 font-devanagari truncate">
                {isHi ? 'अपलोड किए गए पृष्ठ' : 'Uploaded Pages'}
              </p>
              <p className="text-xl font-bold text-stone-900 font-sans tracking-tight">
                {metrics.uploaded}
              </p>
            </div>
          </div>

          <div className="bg-white p-4 rounded-2xl border border-stone-200/90 shadow-2xs flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-700 flex items-center justify-center shrink-0 border border-amber-200">
              <Sparkles className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-semibold text-stone-500 font-devanagari truncate">
                {isHi ? 'OCR सम्पन्न' : 'OCR Completed'}
              </p>
              <p className="text-xl font-bold text-stone-900 font-sans tracking-tight">
                {metrics.ocr_done}
              </p>
            </div>
          </div>

          <div className="bg-white p-4 rounded-2xl border border-stone-200/90 shadow-2xs flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center shrink-0 border border-emerald-200">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-semibold text-stone-500 font-devanagari truncate">
                {isHi ? 'सत्यापित पृष्ठ' : 'Verified Pages'}
              </p>
              <p className="text-xl font-bold text-emerald-800 font-sans tracking-tight">
                {metrics.verified}
              </p>
            </div>
          </div>

          <div className="col-span-2 sm:col-span-1 bg-white p-4 rounded-2xl border border-stone-200/90 shadow-2xs flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-700 flex items-center justify-center shrink-0 border border-purple-200">
              <Layers className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-semibold text-stone-500 font-devanagari truncate">
                {isHi ? 'ग्रन्थों में सुरक्षित' : 'Mapped in Books'}
              </p>
              <p className="text-xl font-bold text-stone-900 font-sans tracking-tight">
                {metrics.added_to_book}
              </p>
            </div>
          </div>
        </div>

        {/* Search & Status Filters */}
        <div className="bg-white p-4 rounded-2xl border border-stone-200/90 shadow-2xs flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
          {/* Search Box */}
          <div className="relative flex-1 min-w-0">
            <Search className="w-4 h-4 text-stone-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={isHi ? 'ग्रन्थ का नाम अथवा विवरण खोजें...' : 'Search books by title or description...'}
              className="w-full pl-9 pr-8 py-2 rounded-xl bg-stone-50 border border-stone-200 focus:bg-white focus:border-vedic-600 focus:ring-2 focus:ring-vedic-500/10 text-xs sm:text-sm font-devanagari text-stone-900 outline-hidden transition-all"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-600 p-0.5"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Status Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 shrink-0">
            {[
              { id: 'all', labelHi: 'सभी', labelEn: 'All' },
              { id: 'in_progress', labelHi: 'प्रगति पर', labelEn: 'In Progress' },
              { id: 'draft', labelHi: 'प्रारूप', labelEn: 'Draft' },
              { id: 'completed', labelHi: 'पूर्ण', labelEn: 'Completed' }
            ].map((st) => (
              <button
                key={st.id}
                type="button"
                onClick={() => setStatusFilter(st.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold font-devanagari transition-all shrink-0 ${
                  statusFilter === st.id
                    ? 'bg-vedic-700 text-white shadow-2xs'
                    : 'bg-stone-100 text-stone-600 hover:text-stone-900 hover:bg-stone-200/80'
                }`}
              >
                {isHi ? st.labelHi : st.labelEn}
              </button>
            ))}
          </div>
        </div>

        {/* Error Notification */}
        {errorMsg && (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-devanagari flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{errorMsg}</span>
            </div>
            <button type="button" onClick={() => setErrorMsg(null)} className="text-rose-500 hover:text-rose-800">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Loading State */}
        {isLoading && (
          <div className="p-12 text-center bg-white rounded-3xl border border-stone-200/90 shadow-2xs my-4">
            <RefreshCw className="w-8 h-8 animate-spin text-vedic-700 mx-auto mb-3" />
            <p className="text-sm font-semibold text-vedic-950 font-devanagari">
              {isHi ? 'ग्रन्थ सूची एवं प्रगति विश्लेषण लोड हो रहा है...' : 'Loading books and preservation progress...'}
            </p>
          </div>
        )}

        {/* Empty State */}
        {!isLoading && filteredBooks.length === 0 && (
          <div className="p-8 sm:p-14 text-center bg-white rounded-3xl border border-stone-200/90 shadow-2xs max-w-xl mx-auto my-8">
            <div className="w-16 h-16 rounded-2xl bg-vedic-50 border border-vedic-200 text-vedic-700 flex items-center justify-center mx-auto mb-4 shadow-2xs font-traditional font-bold text-2xl">
              पु
            </div>
            <h3 className="text-lg font-bold text-stone-900 font-devanagari mb-1">
              {searchQuery || statusFilter !== 'all'
                ? (isHi ? 'कोई ग्रन्थ नहीं मिला' : 'No matching books found')
                : (isHi ? 'पुस्तकालय में कोई ग्रन्थ नहीं है' : 'Your book library is empty')}
            </h3>
            <p className="text-xs sm:text-sm text-stone-500 font-devanagari mb-6 max-w-sm mx-auto">
              {searchQuery || statusFilter !== 'all'
                ? (isHi ? 'कृपया अपना खोज शब्द अथवा फ़िल्टर बदलें।' : 'Try adjusting your search query or status filter.')
                : (isHi 
                    ? 'अपनी दुर्लभ पाण्डुलिपियों एवं धार्मिक पुस्तकों के बहु-पृष्ठीय संरक्षण हेतु पहला ग्रन्थ बनाएं।'
                    : 'Create your first book container to begin multi-page manuscript preservation.')}
            </p>
            <button
              type="button"
              onClick={handleOpenCreate}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-vedic-700 hover:bg-vedic-800 text-white font-bold text-sm shadow-xs font-devanagari transition-colors"
            >
              <Plus className="w-4 h-4" />
              <span>{isHi ? 'नया ग्रन्थ जोड़ें' : 'Add First Book'}</span>
            </button>
          </div>
        )}

        {/* Book Cards Grid */}
        {!isLoading && filteredBooks.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5 sm:gap-6">
            {filteredBooks.map((book) => {
              const verifiedPages = book.verified_pages ?? book.progress?.verified_pages ?? 0;
              const totalPages = book.total_pages || 400;
              const pct = book.progress_percentage ?? (totalPages > 0 ? Math.min(Math.round((verifiedPages / totalPages) * 100), 100) : 0);
              const ocrPages = book.ocr_done_pages ?? book.progress?.ocr_done_pages ?? 0;

              return (
                <div
                  key={book.id}
                  className="bg-white rounded-2xl border border-stone-200/90 shadow-2xs hover:shadow-md transition-all duration-300 flex flex-col overflow-hidden group hover:border-vedic-300"
                >
                  {/* Card Cover Area */}
                  <div
                    onClick={() => handleNavigateToBook(book.id)}
                    className="relative aspect-16/10 bg-vedic-950 overflow-hidden cursor-pointer select-none"
                  >
                    {book.cover_image_url ? (
                      <img
                        src={getStorageUrl(book.cover_image_url)}
                        alt={book.name}
                        loading="lazy"
                        decoding="async"
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500 opacity-90 group-hover:opacity-100"
                        onError={(e) => {
                          // Fallback on image load error
                          e.currentTarget.style.display = 'none';
                        }}
                      />
                    ) : (
                      <div className="w-full h-full bg-gradient-to-br from-vedic-950 via-vedic-900 to-amber-950 flex flex-col items-center justify-center p-4 text-center relative">
                        {/* Decorative traditional corner border accents */}
                        <div className="absolute inset-2 border border-amber-500/20 rounded-lg pointer-events-none" />
                        <div className="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-200 font-traditional text-2xl font-bold mb-2 shadow-inner">
                          {book.name ? book.name.charAt(0) : 'ग्र'}
                        </div>
                        <span className="text-amber-100/90 font-devanagari text-xs font-semibold line-clamp-1 px-2">
                          {book.name}
                        </span>
                        <span className="text-[10px] text-amber-400/70 font-devanagari mt-0.5">
                          {book.language === 'san' ? 'संस्कृत पाण्डुलिपि' : 'हिन्दी ग्रन्थ'}
                        </span>
                      </div>
                    )}

                    {/* Status Badge */}
                    <div className="absolute top-2.5 right-2.5">
                      {book.status === 'completed' ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-300 shadow-xs">
                          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                          <span>{isHi ? 'पूर्ण' : 'Completed'}</span>
                        </span>
                      ) : book.status === 'in_progress' ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-300 shadow-xs">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                          <span>{isHi ? 'प्रगति पर' : 'In Progress'}</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-stone-100 text-stone-700 border border-stone-300 shadow-xs">
                          <Clock className="w-3 h-3 text-stone-500" />
                          <span>{isHi ? 'प्रारूप' : 'Draft'}</span>
                        </span>
                      )}
                    </div>

                    {/* Language Tag */}
                    <div className="absolute bottom-2.5 left-2.5">
                      <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-black/60 backdrop-blur-xs text-white border border-white/10 uppercase tracking-wider">
                        {book.language === 'san' ? 'संस्कृत' : 'हिन्दी'}
                      </span>
                    </div>
                  </div>

                  {/* Card Body */}
                  <div className="p-4 flex-1 flex flex-col justify-between">
                    <div>
                      <h3
                        onClick={() => handleNavigateToBook(book.id)}
                        className="font-devanagari font-bold text-base text-vedic-950 line-clamp-2 hover:text-vedic-700 transition-colors cursor-pointer"
                        title={book.name}
                      >
                        {book.name}
                      </h3>
                      {book.description && (
                        <p className="text-xs text-stone-500 font-devanagari line-clamp-2 mt-1">
                          {book.description}
                        </p>
                      )}
                    </div>

                    {/* Progress Section */}
                    <div className="mt-4 pt-3 border-t border-stone-100 space-y-1.5">
                      <div className="flex items-center justify-between text-xs font-devanagari">
                        <span className="text-stone-500 font-medium">
                          {isHi ? 'सत्यापन प्रगति' : 'Verification'}
                        </span>
                        <span className="font-bold text-vedic-950 font-sans">
                          {pct}%
                        </span>
                      </div>

                      {/* Progress Bar */}
                      <div className="w-full h-2 bg-stone-100 rounded-full overflow-hidden border border-stone-200/80">
                        <div
                          className="h-full bg-gradient-to-r from-vedic-600 to-emerald-600 rounded-full transition-all duration-500"
                          style={{ width: `${Math.max(pct, 2)}%` }}
                        />
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-stone-500 font-devanagari pt-0.5">
                        <span>
                          {verifiedPages} / {totalPages} {isHi ? 'पृष्ठ' : 'pages'}
                        </span>
                        {ocrPages > 0 && (
                          <span className="text-stone-400">
                            {ocrPages} {isHi ? 'OCR' : 'scanned'}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Actions Footer */}
                    <div className="mt-4 pt-3 border-t border-stone-100 flex items-center justify-between gap-2">
                      <button
                        type="button"
                        onClick={() => setBookForReorder(book)}
                        className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-xl bg-vedic-50 hover:bg-vedic-100 text-vedic-800 font-bold text-xs font-devanagari transition-colors border border-vedic-200"
                        title={isHi ? 'पृष्ठ प्रबन्धन व पुनःक्रमबद्ध करें' : 'Manage and reorder pages'}
                      >
                        <ArrowUpDown className="w-3.5 h-3.5 text-saffron-600" />
                        <span>{isHi ? 'पृष्ठ क्रम' : 'Pages'}</span>
                      </button>

                      {onOpenLibrary && (
                        <button
                          type="button"
                          onClick={() => onOpenLibrary(book.id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-vedic-700 hover:bg-vedic-800 text-white font-bold text-xs font-devanagari transition-colors shadow-2xs"
                          title={isHi ? 'पुस्तकालय व भजन वाचन' : 'Open Library'}
                        >
                          <BookMarked className="w-3.5 h-3.5 text-amber-300" />
                          <span>{isHi ? 'पुस्तकालय' : 'Library'}</span>
                        </button>
                      )}
                      {onOpenBookBuilder && (
                        <button
                          type="button"
                          onClick={() => onOpenBookBuilder(book.id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-300 font-bold text-xs font-devanagari transition-colors shadow-2xs"
                          title={isHi ? 'पुस्तक संकलक खोलें' : 'Open Book Builder'}
                        >
                          <Layers className="w-3.5 h-3.5 text-vedic-700" />
                          <span>{isHi ? 'संकलक' : 'Builder'}</span>
                        </button>
                      )}
                      {onOpenVerify && (
                        <button
                          type="button"
                          onClick={() => onOpenVerify(book.id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-900 border border-emerald-300 font-bold text-xs font-devanagari transition-colors shadow-2xs"
                          title={isHi ? 'मानवीय सत्यापन व वर्तनी शुद्धि' : 'Verify & Learn'}
                        >
                          <BrainCircuit className="w-3.5 h-3.5 text-emerald-700" />
                          <span>{isHi ? 'सत्यापन' : 'Verify'}</span>
                        </button>
                      )}
                      {onOpenLearning && (
                        <button
                          type="button"
                          onClick={() => onOpenLearning(book.id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-purple-50 hover:bg-purple-100 text-purple-900 border border-purple-300 font-bold text-xs font-devanagari transition-colors shadow-2xs"
                          title={isHi ? 'एआई अधिगम सांख्यिकी एवं मॉडल डैशबोर्ड' : 'AI Learning Dashboard'}
                        >
                          <Sparkles className="w-3.5 h-3.5 text-purple-700" />
                          <span>{isHi ? 'डैशबोर्ड' : 'AI'}</span>
                        </button>
                      )}
                      {onOpenExport && (
                        <button
                          type="button"
                          onClick={() => onOpenExport(book.id)}
                          className="p-1.5 rounded-lg text-emerald-700 hover:text-emerald-900 hover:bg-emerald-50 transition-colors border border-transparent hover:border-emerald-200"
                          title={isHi ? 'ग्रन्थ निर्यात (DOCX, PDF, TXT...)' : 'Export book'}
                          aria-label="Export book"
                        >
                          <Download className="w-4 h-4 text-emerald-700" />
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleNavigateToBook(book.id)}
                        className="p-1.5 rounded-lg text-stone-500 hover:text-stone-900 hover:bg-stone-100 transition-colors border border-transparent hover:border-stone-200"
                        title={isHi ? 'ग्रन्थ खोलें' : 'Open book'}
                        aria-label="Open book"
                      >
                        <BookOpen className="w-4 h-4 text-vedic-700" />
                      </button>

                      <button
                        type="button"
                        onClick={() => handleOpenEdit(book)}
                        className="p-1.5 rounded-lg text-stone-500 hover:text-stone-900 hover:bg-stone-100 transition-colors border border-transparent hover:border-stone-200"
                        title={isHi ? 'संपादित करें' : 'Edit book details'}
                        aria-label="Edit book"
                      >
                        <Edit3 className="w-4 h-4" />
                      </button>

                      <button
                        type="button"
                        onClick={() => setBookToDelete(book)}
                        className="p-1.5 rounded-lg text-rose-500 hover:text-rose-700 hover:bg-rose-50 transition-colors border border-transparent hover:border-rose-200"
                        title={isHi ? 'ग्रन्थ हटाएं' : 'Delete book'}
                        aria-label="Delete book"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* CREATE BOOK MODAL */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white rounded-3xl border border-stone-200 shadow-xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-200 my-8">
            <div className="px-6 py-5 border-b border-stone-100 flex items-center justify-between bg-stone-50/50">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-vedic-100 text-vedic-700 flex items-center justify-center">
                  <BookOpen className="w-4 h-4" />
                </div>
                <h3 className="text-base sm:text-lg font-bold text-stone-900 font-devanagari">
                  {isHi ? 'नया ग्रन्थ पंजीकृत करें' : 'Create New Book'}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setIsCreateOpen(false)}
                className="text-stone-400 hover:text-stone-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-devanagari flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              {/* Book Name */}
              <div>
                <label className="block text-xs font-bold text-stone-700 font-devanagari mb-1">
                  {isHi ? 'ग्रन्थ का नाम / शीर्षक *' : 'Book Title *'}
                </label>
                <input
                  type="text"
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder={isHi ? 'उदा. श्री ब्रह्मानंद जन्मला भजन माला' : 'e.g. Shree Bramhanand Janmala Bhajan Mala'}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-stone-50 border border-stone-200 focus:bg-white focus:border-vedic-600 focus:ring-2 focus:ring-vedic-500/10 text-sm font-devanagari text-stone-900 outline-hidden transition-all"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-xs font-bold text-stone-700 font-devanagari mb-1">
                  {isHi ? 'विवरण / ऐतिहासिक परिचय (वैकल्पिक)' : 'Description (Optional)'}
                </label>
                <textarea
                  rows={2}
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder={isHi ? 'उदा. दुर्लभ लिथो मुद्रित भजन एवं पद संग्रह, संवत १९८०...' : 'e.g. Rare litho printed devotional hymns...'}
                  className="w-full px-3.5 py-2 rounded-xl bg-stone-50 border border-stone-200 focus:bg-white focus:border-vedic-600 focus:ring-2 focus:ring-vedic-500/10 text-xs font-devanagari text-stone-900 outline-hidden transition-all resize-none"
                />
              </div>

              {/* Language & Total Pages */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-stone-700 font-devanagari mb-1">
                    {isHi ? 'मूल भाषा' : 'Language'}
                  </label>
                  <select
                    value={formLanguage}
                    onChange={(e) => setFormLanguage(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl bg-stone-50 border border-stone-200 focus:bg-white focus:border-vedic-600 text-xs font-devanagari text-stone-900 outline-hidden"
                  >
                    <option value="hin">हिन्दी (Hindi)</option>
                    <option value="san">संस्कृत (Sanskrit)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-stone-700 font-devanagari mb-1">
                    {isHi ? 'कुल पृष्ठ (अनुमानित)' : 'Total Pages'}
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={formTotalPages}
                    onChange={(e) => setFormTotalPages(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-xl bg-stone-50 border border-stone-200 focus:bg-white focus:border-vedic-600 text-xs font-sans text-stone-900 outline-hidden"
                  />
                </div>
              </div>

              {/* Cover Image Upload */}
              <div>
                <label className="block text-xs font-bold text-stone-700 font-devanagari mb-1">
                  {isHi ? 'मुखपृष्ठ छवि (वैकल्पिक)' : 'Cover Image (Optional)'}
                </label>

                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleCoverFileChange}
                  accept="image/png,image/jpeg,image/webp"
                  className="hidden"
                />

                {formCoverPreview ? (
                  <div className="relative rounded-xl overflow-hidden border border-stone-200 h-28 bg-stone-100 flex items-center justify-center">
                    <img src={formCoverPreview} alt="Preview" className="w-full h-full object-cover" />
                    <button
                      type="button"
                      onClick={() => {
                        setFormCoverPreview('');
                        setFormCoverUrl('');
                    
                      }}
                      className="absolute top-2 right-2 p-1 rounded-full bg-black/60 text-white hover:bg-black"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="w-full py-4 px-3 rounded-xl border border-dashed border-stone-300 hover:border-vedic-500 bg-stone-50/50 hover:bg-vedic-50/30 text-stone-500 hover:text-vedic-800 transition-colors flex flex-col items-center justify-center gap-1.5"
                  >
                    <ImageIcon className="w-6 h-6 text-stone-400" />
                    <span className="text-xs font-devanagari font-medium">
                      {isHi ? 'मुखपृष्ठ संचिका चुनें (PNG, JPG)' : 'Choose cover image (PNG, JPG)'}
                    </span>
                  </button>
                )}
              </div>

              {/* Action Buttons */}
              <div className="pt-3 border-t border-stone-100 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-4 py-2 rounded-xl text-stone-600 hover:bg-stone-100 text-xs font-semibold font-devanagari"
                >
                  {isHi ? 'रद्द करें' : 'Cancel'}
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2.5 rounded-xl bg-vedic-700 hover:bg-vedic-800 active:bg-vedic-900 text-white font-bold text-xs font-devanagari shadow-xs disabled:opacity-50 transition-all"
                >
                  {isSubmitting ? (isHi ? 'सुरक्षित हो रहा है...' : 'Saving...') : (isHi ? 'ग्रन्थ सुरक्षित करें' : 'Create Book')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EDIT BOOK MODAL */}
      {isEditOpen && bookToEdit && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white rounded-3xl border border-stone-200 shadow-xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-200 my-8">
            <div className="px-6 py-5 border-b border-stone-100 flex items-center justify-between bg-stone-50/50">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-vedic-100 text-vedic-700 flex items-center justify-center">
                  <Edit3 className="w-4 h-4" />
                </div>
                <h3 className="text-base sm:text-lg font-bold text-stone-900 font-devanagari">
                  {isHi ? 'ग्रन्थ विवरण संपादित करें' : 'Edit Book Details'}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setIsEditOpen(false)}
                className="text-stone-400 hover:text-stone-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleEditSubmit} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-devanagari flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              {/* Book Name */}
              <div>
                <label className="block text-xs font-bold text-stone-700 font-devanagari mb-1">
                  {isHi ? 'ग्रन्थ का नाम / शीर्षक *' : 'Book Title *'}
                </label>
                <input
                  type="text"
                  required
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-stone-50 border border-stone-200 focus:bg-white focus:border-vedic-600 focus:ring-2 focus:ring-vedic-500/10 text-sm font-devanagari text-stone-900 outline-hidden transition-all"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-xs font-bold text-stone-700 font-devanagari mb-1">
                  {isHi ? 'विवरण' : 'Description'}
                </label>
                <textarea
                  rows={2}
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl bg-stone-50 border border-stone-200 focus:bg-white focus:border-vedic-600 text-xs font-devanagari text-stone-900 outline-hidden resize-none"
                />
              </div>

              {/* Language, Total Pages & Status */}
              <div className="grid grid-cols-3 gap-2.5">
                <div>
                  <label className="block text-xs font-bold text-stone-700 font-devanagari mb-1">
                    {isHi ? 'भाषा' : 'Language'}
                  </label>
                  <select
                    value={formLanguage}
                    onChange={(e) => setFormLanguage(e.target.value)}
                    className="w-full px-2.5 py-2 rounded-xl bg-stone-50 border border-stone-200 text-xs font-devanagari text-stone-900 outline-hidden"
                  >
                    <option value="hin">हिन्दी</option>
                    <option value="san">संस्कृत</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-stone-700 font-devanagari mb-1">
                    {isHi ? 'कुल पृष्ठ' : 'Pages'}
                  </label>
                  <input
                    type="number"
                    min={1}
                    value={formTotalPages}
                    onChange={(e) => setFormTotalPages(Number(e.target.value))}
                    className="w-full px-2.5 py-2 rounded-xl bg-stone-50 border border-stone-200 text-xs font-sans text-stone-900 outline-hidden"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-stone-700 font-devanagari mb-1">
                    {isHi ? 'स्थिति' : 'Status'}
                  </label>
                  <select
                    value={formStatus}
                    onChange={(e) => setFormStatus(e.target.value as BookStatus)}
                    className="w-full px-2.5 py-2 rounded-xl bg-stone-50 border border-stone-200 text-xs font-devanagari text-stone-900 outline-hidden font-semibold"
                  >
                    <option value="draft">{isHi ? 'प्रारूप (Draft)' : 'Draft'}</option>
                    <option value="in_progress">{isHi ? 'प्रगति पर' : 'In Progress'}</option>
                    <option value="completed">{isHi ? 'पूर्ण' : 'Completed'}</option>
                  </select>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-3 border-t border-stone-100 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setIsEditOpen(false)}
                  className="px-4 py-2 rounded-xl text-stone-600 hover:bg-stone-100 text-xs font-semibold font-devanagari"
                >
                  {isHi ? 'रद्द करें' : 'Cancel'}
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-5 py-2.5 rounded-xl bg-vedic-700 hover:bg-vedic-800 active:bg-vedic-900 text-white font-bold text-xs font-devanagari shadow-xs disabled:opacity-50 transition-all"
                >
                  {isSubmitting ? (isHi ? 'अद्यतन हो रहा है...' : 'Updating...') : (isHi ? 'परिवर्तन सुरक्षित करें' : 'Save Changes')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DELETE CONFIRMATION MODAL */}
      {bookToDelete && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl border border-stone-200 shadow-xl max-w-md w-full overflow-hidden p-6 space-y-4 animate-in fade-in zoom-in-95 duration-200">
            <div className="w-12 h-12 rounded-2xl bg-rose-50 border border-rose-200 text-rose-600 flex items-center justify-center mx-auto">
              <Trash2 className="w-6 h-6" />
            </div>

            <div className="text-center">
              <h3 className="text-base font-bold text-stone-900 font-devanagari">
                {isHi ? 'ग्रन्थ एवं सम्बन्धित पृष्ठ हटाएं?' : 'Delete Book & Associated Pages?'}
              </h3>
              <p className="text-xs text-stone-600 font-devanagari mt-1.5 leading-relaxed">
                {isHi ? (
                  <>
                    ग्रन्थ <strong className="text-stone-900">{bookToDelete.name}</strong> और इसके अंतर्गत आने वाले सभी पृष्ठ व OCR परिणाम स्थायी रूप से हटा दिए जाएंगे। क्या आप निश्चित हैं?
                  </>
                ) : (
                  <>
                    Are you sure you want to permanently delete <strong className="text-stone-900">{bookToDelete.name}</strong> and all related pages and OCR results?
                  </>
                )}
              </p>
            </div>

            <div className="pt-2 flex items-center justify-center gap-3">
              <button
                type="button"
                onClick={() => setBookToDelete(null)}
                className="flex-1 px-4 py-2.5 rounded-xl border border-stone-200 text-stone-700 hover:bg-stone-50 font-semibold text-xs font-devanagari transition-colors"
              >
                {isHi ? 'रद्द करें' : 'Cancel'}
              </button>
              <button
                type="button"
                disabled={isSubmitting}
                onClick={handleDeleteConfirm}
                className="flex-1 px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white font-bold text-xs font-devanagari shadow-xs transition-colors disabled:opacity-50"
              >
                {isSubmitting ? (isHi ? 'हट रहा है...' : 'Deleting...') : (isHi ? 'हाँ, हटाएं' : 'Yes, Delete')}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* BOOK PAGE REORDER MODAL */}
      <BookPageReorderModal
        book={bookForReorder}
        isOpen={!!bookForReorder}
        onClose={() => setBookForReorder(null)}
        lang={lang}
        onBookUpdated={loadBooksData}
      />
    </div>
  );
};
