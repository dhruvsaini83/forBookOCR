import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
  ArrowLeft, BookOpen, CheckCircle2, Copy, Check, Trash2,
  GripVertical, Plus, RefreshCw, Save, Layers,
  Search, Sparkles, FileText, CheckSquare,
  Square, AlertCircle, ChevronDown, ChevronUp, ShieldCheck
} from 'lucide-react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { api, getStorageUrl } from '../services/api';
import type { BookData, PageData, BookBuilderData } from '../types';
import type { Language } from '../i18n/translations';

interface BookBuilderProps {
  initialBookId?: string;
  lang?: Language;
  onNavigateBack?: () => void;
  onNavigateHome?: () => void;
  onOpenCombinedEditor?: (bookId: string) => void;
}

// ---------------------------------------------------------
// Helper: Check if page has completed/verified text
// ---------------------------------------------------------
export const isPageVerified = (page: PageData): boolean => {
  const statusUpper = (page.status || '').toUpperCase();
  const hasConfirmed = Boolean(page.confirmed_text && page.confirmed_text.trim());
  const hasVerified = Boolean(page.verified_text && page.verified_text.trim());
  return statusUpper === 'COMPLETED' || statusUpper === 'VERIFIED' || hasConfirmed || hasVerified;
};

// ---------------------------------------------------------
// Helper: Get verified text snippet
// ---------------------------------------------------------
const getPageTextSnippet = (page: PageData): string => {
  return (page.confirmed_text || page.reviewed_text || page.verified_text || page.raw_ocr_text || '').trim();
};

// ---------------------------------------------------------
// Subcomponent: Sortable Included Page Block (70% Center/Right)
// ---------------------------------------------------------
interface SortableBlockProps {
  page: PageData;
  index: number;
  isSelectedForCopy: boolean;
  onToggleSelectCopy: (pageId: string) => void;
  onRemove: (pageId: string) => void;
  onSingleCopy: (page: PageData) => void;
  isHi: boolean;
}

const SortableBlock: React.FC<SortableBlockProps> = ({
  page,
  index,
  isSelectedForCopy,
  onToggleSelectCopy,
  onRemove,
  onSingleCopy,
  isHi
}) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: page.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 40 : 'auto',
    opacity: isDragging ? 0.6 : 1
  };

  const [isExpanded, setIsExpanded] = useState<boolean>(true);
  const [copiedLocal, setCopiedLocal] = useState<boolean>(false);

  const textContent = getPageTextSnippet(page);
  const wordCount = textContent ? textContent.split(/\s+/).filter(Boolean).length : 0;
  const charCount = textContent.length;

  const handleCopy = () => {
    onSingleCopy(page);
    setCopiedLocal(true);
    setTimeout(() => setCopiedLocal(false), 2000);
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`rounded-2xl border transition-all duration-200 bg-white shadow-2xs overflow-hidden ${
        isDragging
          ? 'border-vedic-500 shadow-xl ring-2 ring-vedic-400/20 bg-amber-50/60'
          : 'border-stone-200/90 hover:border-stone-300'
      }`}
    >
      {/* Block Header */}
      <div className="flex items-center justify-between px-3.5 py-2.5 bg-stone-50 border-b border-stone-200/80 gap-2 flex-wrap">
        <div className="flex items-center gap-2 min-w-0">
          {/* Drag Handle */}
          <button
            type="button"
            {...attributes}
            {...listeners}
            className="cursor-grab active:cursor-grabbing p-1 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-200/70 transition-colors shrink-0"
            title={isHi ? 'क्रम बदलने हेतु खींचें' : 'Drag to reorder'}
            aria-label="Drag handle"
          >
            <GripVertical className="w-4 h-4" />
          </button>

          {/* Copy Selection Checkbox */}
          <button
            type="button"
            onClick={() => onToggleSelectCopy(page.id)}
            className="text-stone-500 hover:text-vedic-700 transition-colors shrink-0"
            title={isHi ? 'कॉपी हेतु चयन करें' : 'Select for copy'}
          >
            {isSelectedForCopy ? (
              <CheckSquare className="w-4 h-4 text-vedic-700" />
            ) : (
              <Square className="w-4 h-4 text-stone-400" />
            )}
          </button>

          {/* Page Number Title */}
          <span className="font-devanagari font-bold text-xs sm:text-sm text-stone-900 truncate">
            {isHi ? `पृष्ठ ${page.page_number}` : `Page ${page.page_number}`}
          </span>

          <span className="text-[10px] sm:text-xs font-mono text-stone-400 bg-white px-1.5 py-0.5 rounded border border-stone-200 shrink-0">
            #{index + 1}
          </span>
        </div>

        {/* Action Buttons in Block Header */}
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="text-[11px] text-stone-500 font-devanagari hidden md:inline">
            {wordCount} शब्द | {charCount} वर्ण
          </span>

          {/* Single Page Copy Button */}
          <button
            type="button"
            onClick={handleCopy}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-devanagari border border-stone-200 bg-white hover:bg-stone-100 text-stone-700 transition-colors shadow-2xs"
            title={isHi ? 'इस पृष्ठ का पाठ कॉपी करें' : 'Copy page text'}
          >
            {copiedLocal ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-600" />
                <span className="text-emerald-700 font-semibold text-[11px]">
                  {isHi ? 'कॉपी हुआ' : 'Copied'}
                </span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5 text-stone-500" />
                <span className="text-[11px] hidden sm:inline">{isHi ? 'कॉपी' : 'Copy'}</span>
              </>
            )}
          </button>

          {/* Expand / Collapse Button */}
          <button
            type="button"
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-100 transition-colors"
            title={isExpanded ? (isHi ? 'संक्षिप्त करें' : 'Collapse') : (isHi ? 'विस्तार करें' : 'Expand')}
          >
            {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>

          {/* Remove Button */}
          <button
            type="button"
            onClick={() => onRemove(page.id)}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-devanagari border border-rose-200 bg-rose-50/70 hover:bg-rose-100 text-rose-700 transition-colors shadow-2xs ml-1"
            title={isHi ? 'पुस्तक संकलक से हटाएं' : 'Remove from book builder'}
          >
            <Trash2 className="w-3.5 h-3.5 text-rose-600" />
            <span className="text-[11px] font-medium hidden sm:inline">{isHi ? 'हटाएं' : 'Remove'}</span>
          </button>
        </div>
      </div>

      {/* Block Body / Text Area */}
      {isExpanded && (
        <div className="p-3.5 sm:p-4 bg-white">
          <div className="font-devanagari text-xs sm:text-sm text-stone-800 leading-relaxed whitespace-pre-wrap selection:bg-amber-100 select-text bg-[#fcfbfa] p-3 rounded-xl border border-stone-100">
            {textContent || (
              <span className="text-stone-400 italic font-devanagari">
                {isHi ? '(इस पृष्ठ पर कोई सत्यापित पाठ उपलब्ध नहीं है)' : '(No verified text on this page)'}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

// ---------------------------------------------------------
// Main BookBuilder Component
// ---------------------------------------------------------
export const BookBuilder: React.FC<BookBuilderProps> = ({
  initialBookId,
  lang = 'hi',
  onNavigateBack,
  onNavigateHome: _onNavigateHome,
  onOpenCombinedEditor
}) => {
  const isHi = lang === 'hi';

  // State: Book Selection
  const [booksList, setBooksList] = useState<BookData[]>([]);
  const [selectedBookId, setSelectedBookId] = useState<string>(initialBookId || '');
  const [activeBook, setActiveBook] = useState<BookData | null>(null);
  void activeBook;

  // State: Left Panel Available Pages
  const [allPages, setAllPages] = useState<PageData[]>([]);
  const [onlyVerifiedFilter, setOnlyVerifiedFilter] = useState<boolean>(true);
  const [searchPageQuery, setSearchPageQuery] = useState<string>('');
  const [selectedPageIdsForAdd, setSelectedPageIdsForAdd] = useState<string[]>([]);

  // State: Center/Right Panel Builder Data
  const [builderData, setBuilderData] = useState<BookBuilderData | null>(null);
  const [includedPages, setIncludedPages] = useState<PageData[]>([]);
  const [combinedText, setCombinedText] = useState<string>('');
  const [activeViewMode, setActiveViewMode] = useState<'blocks' | 'editor' | 'split'>('blocks');
  const [selectedBlockIdsForCopy, setSelectedBlockIdsForCopy] = useState<string[]>([]);

  // State: Loading, Errors & Auto-Save
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isAddingPages, setIsAddingPages] = useState<boolean>(false);
  const [isUpdatingOrder, setIsUpdatingOrder] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Auto-Save Draft State
  const [isDirty, setIsDirty] = useState<boolean>(false);
  const [isSavingDraft, setIsSavingDraft] = useState<boolean>(false);
  const [lastSavedTime, setLastSavedTime] = useState<Date | null>(null);
  const [draftBannerVisible, setDraftBannerVisible] = useState<boolean>(false);

  // Copy Feedback
  const [copiedComplete, setCopiedComplete] = useState<boolean>(false);
  const [copiedSelected, setCopiedSelected] = useState<boolean>(false);

  // Refs for auto-save
  const textRef = useRef<string>(combinedText);
  textRef.current = combinedText;
  const isDirtyRef = useRef<boolean>(isDirty);
  isDirtyRef.current = isDirty;
  const selectedBookIdRef = useRef<string>(selectedBookId);
  selectedBookIdRef.current = selectedBookId;

  // dnd-kit sensors
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5
      }
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates
    })
  );

  // Show auto-dismissing toast
  const showToast = useCallback((msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage((prev) => (prev === msg ? null : prev));
    }, 3500);
  }, []);

  // ---------------------------------------------------------
  // 1. Initial Load: Fetch All Books
  // ---------------------------------------------------------
  useEffect(() => {
    const fetchBooks = async () => {
      try {
        const res = await api.listBooks();
        if (res && res.books && res.books.length > 0) {
          setBooksList(res.books);
          if (!selectedBookId) {
            setSelectedBookId(res.books[0].id);
          }
        }
      } catch (err: any) {
        console.error('Failed to load books list:', err);
      }
    };
    fetchBooks();
  }, []);

  // ---------------------------------------------------------
  // 2. Load Selected Book's Pages & Builder Data
  // ---------------------------------------------------------
  const loadBookData = useCallback(async (bookId: string) => {
    if (!bookId) return;
    try {
      setIsLoading(true);
      setErrorMessage(null);
      setSelectedPageIdsForAdd([]);
      setSelectedBlockIdsForCopy([]);

      // Fetch Book metadata
      const bookRes = await api.getBook(bookId);
      setActiveBook(bookRes.book);

      // Fetch all pages for this book (sorted by page_number)
      const pagesRes = await api.getBookPages(bookId, 'page_number');
      const fetchedPages = pagesRes.pages || [];
      setAllPages(fetchedPages);

      // Fetch Book Builder collection
      const builderRes = await api.getBookBuilder(bookId);
      if (builderRes && builderRes.builder) {
        setBuilderData(builderRes.builder);
        const bText = builderRes.builder.combined_text || '';
        setCombinedText(bText);
        setIsDirty(false);

        // If there was existing text saved in the draft, show continue banner
        if (bText.trim().length > 0) {
          setDraftBannerVisible(true);
        }

        // Reconstruct includedPages array ordered by builder.page_order
        if (builderRes.pages && builderRes.pages.length > 0) {
          const pageOrder = builderRes.builder.page_order || [];
          const sortedIncluded = [...builderRes.pages].sort((a, b) => {
            const idxA = pageOrder.indexOf(a.page_number);
            const idxB = pageOrder.indexOf(b.page_number);
            if (idxA === -1 && idxB === -1) return a.page_number - b.page_number;
            if (idxA === -1) return 1;
            if (idxB === -1) return -1;
            return idxA - idxB;
          });
          setIncludedPages(sortedIncluded);
        } else {
          setIncludedPages([]);
        }
      }
    } catch (err: any) {
      console.error('Failed to load book builder details:', err);
      setErrorMessage(err.message || (isHi ? 'पुस्तक संकलक डेटा लोड करने में विफल।' : 'Failed to load builder data.'));
    } finally {
      setIsLoading(false);
    }
  }, [isHi]);

  useEffect(() => {
    if (selectedBookId) {
      loadBookData(selectedBookId);
    }
  }, [selectedBookId, loadBookData]);

  // ---------------------------------------------------------
  // 3. Auto-Save Draft: Run every 5 seconds if dirty
  // ---------------------------------------------------------
  useEffect(() => {
    const timer = setInterval(async () => {
      const currentBookId = selectedBookIdRef.current;
      if (isDirtyRef.current && currentBookId && textRef.current !== undefined) {
        try {
          setIsSavingDraft(true);
          await api.builderEditText(currentBookId, textRef.current);
          setIsDirty(false);
          isDirtyRef.current = false;
          setLastSavedTime(new Date());
        } catch (err: any) {
          console.error('Auto-save error:', err);
        } finally {
          setIsSavingDraft(false);
        }
      }
    }, 5000);

    return () => clearInterval(timer);
  }, []);

  // ---------------------------------------------------------
  // 4. Manual Save Draft Button
  // ---------------------------------------------------------
  const handleManualSaveDraft = async () => {
    if (!selectedBookId) return;
    try {
      setIsSavingDraft(true);
      await api.builderEditText(selectedBookId, combinedText);
      setIsDirty(false);
      isDirtyRef.current = false;
      setLastSavedTime(new Date());
      showToast(isHi ? 'ड्राफ्ट सुरक्षित रूप से सहेजा गया! ✓' : 'Draft saved successfully! ✓');
    } catch (err: any) {
      alert((isHi ? 'ड्राफ्ट सहेजने में विफल: ' : 'Failed to save draft: ') + err.message);
    } finally {
      setIsSavingDraft(false);
    }
  };

  // ---------------------------------------------------------
  // 5. Left Panel Filtering & Duplication Set
  // ---------------------------------------------------------
  const includedPageIdSet = useMemo(() => {
    return new Set(builderData?.included_pages || []);
  }, [builderData?.included_pages]);

  const displayedLeftPages = useMemo(() => {
    return allPages.filter((p) => {
      if (onlyVerifiedFilter && !isPageVerified(p)) {
        return false;
      }
      if (searchPageQuery.trim()) {
        const query = searchPageQuery.trim();
        const matchesNum = String(p.page_number).includes(query);
        const snippet = getPageTextSnippet(p).toLowerCase();
        const matchesText = snippet.includes(query.toLowerCase());
        return matchesNum || matchesText;
      }
      return true;
    });
  }, [allPages, onlyVerifiedFilter, searchPageQuery]);

  // ---------------------------------------------------------
  // 6. Add Single Page to Builder (with Duplicate Check)
  // ---------------------------------------------------------
  const handleAddSinglePage = async (page: PageData) => {
    if (!selectedBookId) return;

    // Strict duplicate check: Same page_id cannot be added twice
    if (includedPageIdSet.has(page.id)) {
      alert(isHi 
        ? `पृष्ठ ${page.page_number} पहले से ही इस ग्रन्थ में शामिल है। दोहराव अवरुद्ध किया गया।` 
        : `Page ${page.page_number} is already added. Duplicate addition blocked.`);
      return;
    }

    // Strict verification check
    if (!isPageVerified(page)) {
      alert(isHi 
        ? `पृष्ठ ${page.page_number} अभी सत्यापित नहीं है। केवल सत्यापित पृष्ठ ही ग्रन्थ में जोड़े जा सकते हैं।` 
        : `Page ${page.page_number} is not verified yet. Only verified pages can be added.`);
      return;
    }

    try {
      setIsAddingPages(true);
      const res = await api.builderAddPages(selectedBookId, [page.id]);
      if (res && res.builder) {
        setBuilderData(res.builder);
        setCombinedText(res.builder.combined_text || '');
        setIsDirty(false);
        // Refresh pages
        await loadBookData(selectedBookId);
        showToast(isHi ? `पृष्ठ ${page.page_number} पुस्तक में जोड़ा गया!` : `Page ${page.page_number} added!`);
      }
    } catch (err: any) {
      alert((isHi ? 'पृष्ठ जोड़ने में त्रुटि: ' : 'Error adding page: ') + err.message);
    } finally {
      setIsAddingPages(false);
    }
  };

  // ---------------------------------------------------------
  // 7. Bulk Add Selected Pages (with Duplicate Check)
  // ---------------------------------------------------------
  const handleBulkAddPages = async () => {
    if (!selectedBookId || selectedPageIdsForAdd.length === 0) return;

    // Filter out duplicates and unverified pages
    const validIdsToAdd: string[] = [];
    let duplicateSkipped = 0;
    let unverifiedSkipped = 0;

    for (const pid of selectedPageIdsForAdd) {
      if (includedPageIdSet.has(pid)) {
        duplicateSkipped++;
        continue;
      }
      const pageObj = allPages.find((p) => p.id === pid);
      if (!pageObj || !isPageVerified(pageObj)) {
        unverifiedSkipped++;
        continue;
      }
      validIdsToAdd.push(pid);
    }

    if (validIdsToAdd.length === 0) {
      if (duplicateSkipped > 0) {
        alert(isHi 
          ? `चयनित सभी पृष्ठ पहले से ही जोड़े जा चुके हैं। कोई नया पृष्ठ नहीं जोड़ा गया।` 
          : `All selected pages are already in the book. No new pages added.`);
      } else if (unverifiedSkipped > 0) {
        alert(isHi 
          ? `चयनित पृष्ठ असत्यापित हैं। केवल सत्यापित पृष्ठ ही जोड़े जा सकते हैं।` 
          : `Selected pages are not verified.`);
      }
      return;
    }

    try {
      setIsAddingPages(true);
      const res = await api.builderAddPages(selectedBookId, validIdsToAdd);
      if (res && res.builder) {
        setBuilderData(res.builder);
        setCombinedText(res.builder.combined_text || '');
        setIsDirty(false);
        setSelectedPageIdsForAdd([]);
        await loadBookData(selectedBookId);

        let msg = isHi 
          ? `${validIdsToAdd.length} पृष्ठ सफलतापूर्वक पुस्तक में जोड़े गए!` 
          : `${validIdsToAdd.length} pages added to book!`;
        if (duplicateSkipped > 0) {
          msg += isHi ? ` (${duplicateSkipped} दोहराव छोड़े गए)` : ` (${duplicateSkipped} duplicates skipped)`;
        }
        showToast(msg);
      }
    } catch (err: any) {
      alert((isHi ? 'बल्क पृष्ठ जोड़ने में त्रुटि: ' : 'Error bulk adding pages: ') + err.message);
    } finally {
      setIsAddingPages(false);
    }
  };

  // ---------------------------------------------------------
  // 8. Remove Page from Builder
  // ---------------------------------------------------------
  const handleRemovePage = async (pageId: string) => {
    if (!selectedBookId) return;
    const targetPage = includedPages.find((p) => p.id === pageId);
    const confirmMsg = isHi
      ? `क्या आप पृष्ठ ${targetPage?.page_number || ''} को पुस्तक संकलक से हटाना चाहते हैं? (मूल पृष्ठ का पाठ सुरक्षित रहेगा)`
      : `Remove page ${targetPage?.page_number || ''} from builder? (Original verified text will remain safe)`;

    if (!window.confirm(confirmMsg)) return;

    try {
      setIsAddingPages(true);
      const res = await api.builderRemovePage(selectedBookId, pageId);
      if (res && res.builder) {
        setBuilderData(res.builder);
        setCombinedText(res.builder.combined_text || '');
        setIsDirty(false);
        await loadBookData(selectedBookId);
        showToast(isHi ? 'पृष्ठ संकलक से हटा दिया गया!' : 'Page removed from builder!');
      }
    } catch (err: any) {
      alert((isHi ? 'हटाने में त्रुटि: ' : 'Error removing page: ') + err.message);
    } finally {
      setIsAddingPages(false);
    }
  };

  // ---------------------------------------------------------
  // 9. Reorder Pages via Drag-and-Drop
  // ---------------------------------------------------------
  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id || !selectedBookId) return;

    const oldIndex = includedPages.findIndex((p) => p.id === active.id);
    const newIndex = includedPages.findIndex((p) => p.id === over.id);

    if (oldIndex !== -1 && newIndex !== -1) {
      const reordered = arrayMove(includedPages, oldIndex, newIndex);
      setIncludedPages(reordered);

      const orderedPageNumbers = reordered.map((p) => p.page_number);
      try {
        setIsUpdatingOrder(true);
        const res = await api.builderReorderPages(selectedBookId, orderedPageNumbers);
        if (res && res.builder) {
          setBuilderData(res.builder);
          setCombinedText(res.builder.combined_text || '');
          setIsDirty(false);
          showToast(isHi ? 'पृष्ठ क्रम सफलतापूर्वक बदला गया!' : 'Page order updated!');
        }
      } catch (err: any) {
        console.error('Failed to reorder builder pages:', err);
        await loadBookData(selectedBookId);
      } finally {
        setIsUpdatingOrder(false);
      }
    }
  };

  // ---------------------------------------------------------
  // 10. Copy Complete Book Text
  // ---------------------------------------------------------
  const handleCopyCompleteBook = async () => {
    if (!combinedText || combinedText.trim().length === 0) {
      alert(isHi ? 'कॉपी करने के लिए कोई पाठ उपलब्ध नहीं है।' : 'No text available to copy.');
      return;
    }
    try {
      await navigator.clipboard.writeText(combinedText);
      setCopiedComplete(true);
      showToast(isHi ? 'संपूर्ण पुस्तक पाठ क्लिपबोर्ड पर कॉपी किया गया! ✓' : 'Complete book text copied! ✓');
      setTimeout(() => setCopiedComplete(false), 2500);
    } catch (err) {
      console.error('Failed to copy complete text:', err);
    }
  };

  // ---------------------------------------------------------
  // 11. Copy Selected Pages Text
  // ---------------------------------------------------------
  const handleCopySelectedPages = async () => {
    if (selectedBlockIdsForCopy.length === 0) {
      alert(isHi 
        ? 'कृपया कॉपी करने के लिए कम से कम एक पृष्ठ का चयन करें।' 
        : 'Please select at least one page to copy.');
      return;
    }

    const pagesToCopy = includedPages.filter((p) => selectedBlockIdsForCopy.includes(p.id));
    const separator = builderData?.separator || '\n\n-------------------------\n\n';
    const textPieces = pagesToCopy.map((p) => `Page ${p.page_number}\n${getPageTextSnippet(p)}`);
    const finalCopyText = textPieces.join(separator);

    try {
      await navigator.clipboard.writeText(finalCopyText);
      setCopiedSelected(true);
      showToast(isHi 
        ? `${pagesToCopy.length} चयनित पृष्ठों का पाठ कॉपी हो गया! ✓` 
        : `${pagesToCopy.length} selected pages text copied! ✓`);
      setTimeout(() => setCopiedSelected(false), 2500);
    } catch (err) {
      console.error('Failed to copy selected text:', err);
    }
  };

  // Single page copy handler
  const handleSinglePageCopy = async (page: PageData) => {
    const text = `Page ${page.page_number}\n${getPageTextSnippet(page)}`;
    try {
      await navigator.clipboard.writeText(text);
      showToast(isHi ? `पृष्ठ ${page.page_number} कॉपी किया गया!` : `Page ${page.page_number} copied!`);
    } catch (e) {
      console.error(e);
    }
  };

  // ---------------------------------------------------------
  // 12. Manual Combined Text Editing
  // ---------------------------------------------------------
  const handleManualTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setCombinedText(e.target.value);
    setIsDirty(true);
  };

  // Selection toggle helpers
  const handleTogglePageSelectForAdd = (pageId: string) => {
    setSelectedPageIdsForAdd((prev) =>
      prev.includes(pageId) ? prev.filter((id) => id !== pageId) : [...prev, pageId]
    );
  };

  const handleSelectAllLeftPages = () => {
    // Select all displayed verified pages that are not already added
    const availableIds = displayedLeftPages
      .filter((p) => isPageVerified(p) && !includedPageIdSet.has(p.id))
      .map((p) => p.id);
    setSelectedPageIdsForAdd(availableIds);
  };

  const handleDeselectAllLeftPages = () => {
    setSelectedPageIdsForAdd([]);
  };

  const handleToggleSelectBlockForCopy = (pageId: string) => {
    setSelectedBlockIdsForCopy((prev) =>
      prev.includes(pageId) ? prev.filter((id) => id !== pageId) : [...prev, pageId]
    );
  };

  const handleSelectAllBlocksForCopy = () => {
    setSelectedBlockIdsForCopy(includedPages.map((p) => p.id));
  };

  const handleDeselectAllBlocksForCopy = () => {
    setSelectedBlockIdsForCopy([]);
  };

  return (
    <div className="flex-1 max-w-7xl w-full mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 flex flex-col gap-5">
      {/* Toast Notification Banner */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-3 bg-vedic-950 text-white rounded-2xl shadow-xl border border-vedic-800 flex items-center gap-2.5 font-devanagari text-xs sm:text-sm animate-in fade-in slide-in-from-bottom-3 duration-200">
          <Sparkles className="w-4 h-4 text-amber-400 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Header & Book Selection Navigation Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-3xl bg-white border border-stone-200/90 shadow-2xs">
        <div className="flex items-center gap-3 flex-wrap">
          {onNavigateBack && (
            <button
              type="button"
              onClick={onNavigateBack}
              className="p-2 rounded-xl border border-stone-200 hover:bg-stone-50 text-stone-700 transition-colors shadow-2xs"
              title={isHi ? 'पीछे जाएं' : 'Go back'}
            >
              <ArrowLeft className="w-4 h-4 text-vedic-700" />
            </button>
          )}

          <div className="w-10 h-10 rounded-2xl bg-vedic-100 border border-vedic-200 text-vedic-800 flex items-center justify-center shrink-0">
            <Layers className="w-5 h-5 text-vedic-700" />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base sm:text-lg font-bold text-stone-900 font-devanagari">
                {isHi ? 'ग्रन्थ संकलक (Book Builder)' : 'Heritage Book Builder'}
              </h1>
              <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-vedic-100 text-vedic-800 font-devanagari">
                {isHi ? '५-चरणीय पूर्ण' : 'V2.2'}
              </span>
            </div>
            <p className="text-xs text-stone-500 font-devanagari">
              {isHi
                ? 'सत्यापित पृष्ठों को क्रमित कर सम्पूर्ण ग्रन्थ का डिजिटल संस्करण तैयार करें'
                : 'Compile verified pages, reorder sequence, and export complete book edition'}
            </p>
          </div>
        </div>

        {/* Book Selector Dropdown & Actions */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {booksList.length > 0 && (
            <div className="flex items-center gap-1.5 bg-stone-50 p-1.5 rounded-2xl border border-stone-200">
              <BookOpen className="w-4 h-4 text-vedic-700 ml-1.5 shrink-0" />
              <select
                value={selectedBookId}
                onChange={(e) => setSelectedBookId(e.target.value)}
                className="bg-transparent text-xs sm:text-sm font-semibold text-stone-900 font-devanagari focus:outline-none pr-3 cursor-pointer max-w-[200px] truncate"
              >
                {booksList.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name} ({b.total_pages || 400} पृ.)
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Save Draft Indicator & Button */}
          <div className="flex items-center gap-2">
            <div className="text-[11px] font-devanagari flex items-center gap-1 text-stone-500 px-2">
              {isSavingDraft ? (
                <>
                  <RefreshCw className="w-3 h-3 animate-spin text-vedic-600" />
                  <span className="text-vedic-700">{isHi ? 'सहेजा जा रहा है...' : 'Saving...'}</span>
                </>
              ) : isDirty ? (
                <>
                  <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                  <span className="text-amber-700">{isHi ? 'असंरक्षित बदलाव' : 'Unsaved changes'}</span>
                </>
              ) : lastSavedTime ? (
                <>
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  <span className="text-stone-500">
                    {isHi ? 'सहेजा गया' : 'Saved'}{' '}
                    {lastSavedTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </>
              ) : (
                <span className="text-stone-400">5s {isHi ? 'स्वतः सहेजें सक्रिय' : 'Auto-save on'}</span>
              )}
            </div>

            {onOpenCombinedEditor && selectedBookId && (
              <button
                type="button"
                onClick={() => onOpenCombinedEditor(selectedBookId)}
                className="inline-flex items-center gap-1.5 px-3 sm:px-3.5 py-2 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-300 font-bold text-xs font-devanagari transition-colors shadow-2xs"
                title={isHi ? 'विस्तृत दस्तावेज़ सम्पादक खोलें' : 'Open Combined Document Editor'}
              >
                <FileText className="w-3.5 h-3.5 text-vedic-700" />
                <span>{isHi ? 'दस्तावेज़ सम्पादक' : 'Document Editor'}</span>
              </button>
            )}
            <button
              type="button"
              onClick={handleManualSaveDraft}
              disabled={isSavingDraft || !isDirty}
              className="inline-flex items-center gap-1.5 px-3 sm:px-3.5 py-2 rounded-xl bg-vedic-700 hover:bg-vedic-800 disabled:opacity-50 text-white font-bold text-xs font-devanagari transition-colors shadow-2xs"
            >
              <Save className="w-3.5 h-3.5" />
              <span>{isHi ? 'ड्राफ्ट सहेजें' : 'Save Draft'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Error Message Banner */}
      {errorMessage && (
        <div className="p-3.5 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs sm:text-sm font-devanagari flex items-center justify-between gap-3 shadow-2xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setErrorMessage(null)}
            className="text-rose-500 hover:text-rose-800 font-bold text-xs"
          >
            {isHi ? 'बंद करें' : 'Dismiss'}
          </button>
        </div>
      )}

      {/* Continue From Draft Banner */}
      {draftBannerVisible && builderData?.combined_text && (
        <div className="p-3 sm:p-3.5 rounded-2xl bg-amber-50/90 border border-amber-200/90 text-amber-950 text-xs sm:text-sm font-devanagari flex items-center justify-between gap-3 shadow-2xs">
          <div className="flex items-center gap-2.5">
            <Sparkles className="w-4 h-4 text-amber-600 shrink-0" />
            <span>
              {isHi
                ? `इस ग्रन्थ का पूर्व-सहेजा गया ड्राफ्ट उपलब्ध है (${includedPages.length} पृष्ठ संकलित)। आप इसी ड्राफ्ट से संपादन जारी रख सकते हैं।`
                : `A previously saved draft is available with ${includedPages.length} compiled pages. You are editing this draft.`}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setDraftBannerVisible(false)}
            className="text-amber-700 hover:text-amber-950 font-bold text-xs shrink-0 underline"
          >
            {isHi ? 'ठीक है' : 'Dismiss'}
          </button>
        </div>
      )}

      {/* Main 2-Panel Layout: Left (30%) vs Right (70%) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 sm:gap-6 items-start">
        {/* ========================================================= */}
        {/* LEFT PANEL (30% -> col-span-12 lg:col-span-4): Verified Pages */}
        {/* ========================================================= */}
        <div className="lg:col-span-4 bg-white rounded-3xl border border-stone-200/90 shadow-2xs p-4 flex flex-col gap-3.5">
          {/* Left Panel Header */}
          <div className="flex items-center justify-between pb-2 border-b border-stone-100">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-vedic-700" />
              <h2 className="font-devanagari font-bold text-sm sm:text-base text-stone-900">
                {isHi ? 'उपलब्ध पृष्ठ' : 'Available Pages'}
              </h2>
            </div>
            <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded-full bg-stone-100 text-stone-700 border border-stone-200">
              {displayedLeftPages.length}
            </span>
          </div>

          {/* Filter: Only verified pages toggle */}
          <div className="flex items-center justify-between p-2.5 rounded-xl bg-stone-50 border border-stone-200/80 text-xs font-devanagari">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={onlyVerifiedFilter}
                onChange={(e) => setOnlyVerifiedFilter(e.target.checked)}
                className="w-4 h-4 accent-vedic-700 rounded text-vedic-700 focus:ring-0 cursor-pointer"
              />
              <span className="font-semibold text-stone-800">
                {isHi ? 'केवल सत्यापित पृष्ठ दिखाएं' : 'Show only verified pages'}
              </span>
            </label>
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
          </div>

          {/* Search by page number or text */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchPageQuery}
              onChange={(e) => setSearchPageQuery(e.target.value)}
              placeholder={isHi ? 'पृष्ठ संख्या अथवा शब्द खोजें...' : 'Search page number or text...'}
              className="w-full pl-8 pr-3 py-1.5 text-xs font-devanagari rounded-xl border border-stone-200 focus:outline-none focus:border-vedic-500 bg-white"
            />
          </div>

          {/* Bulk Selection Actions */}
          <div className="flex items-center justify-between gap-2 text-xs font-devanagari pt-1">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleSelectAllLeftPages}
                className="text-vedic-700 hover:text-vedic-900 font-semibold"
              >
                {isHi ? 'सभी चुनें' : 'Select All'}
              </button>
              <span className="text-stone-300">|</span>
              <button
                type="button"
                onClick={handleDeselectAllLeftPages}
                className="text-stone-500 hover:text-stone-800"
              >
                {isHi ? 'अचयनित' : 'Clear'}
              </button>
            </div>

            {/* Bulk Add Button */}
            <button
              type="button"
              onClick={handleBulkAddPages}
              disabled={selectedPageIdsForAdd.length === 0 || isAddingPages}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-vedic-700 hover:bg-vedic-800 disabled:opacity-40 text-white font-bold text-xs shadow-2xs font-devanagari transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>
                {isHi
                  ? `चयनित जोड़ें (${selectedPageIdsForAdd.length})`
                  : `Bulk Add (${selectedPageIdsForAdd.length})`}
              </span>
            </button>
          </div>

          {/* Left Panel Page List (Scrollable) */}
          <div className="flex flex-col gap-2.5 max-h-[720px] overflow-y-auto pr-1">
            {isLoading ? (
              <div className="p-8 text-center text-stone-400 font-devanagari text-xs">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-vedic-600" />
                <span>{isHi ? 'पृष्ठ लोड हो रहे हैं...' : 'Loading pages...'}</span>
              </div>
            ) : displayedLeftPages.length === 0 ? (
              <div className="p-8 text-center bg-stone-50 rounded-2xl border border-stone-200/60 text-stone-500 font-devanagari text-xs">
                {onlyVerifiedFilter ? (
                  <>
                    <AlertCircle className="w-6 h-6 text-amber-500 mx-auto mb-2" />
                    <p className="font-semibold text-stone-800 mb-1">
                      {isHi ? 'कोई सत्यापित पृष्ठ नहीं मिला' : 'No verified pages found'}
                    </p>
                    <p className="text-[11px] text-stone-400">
                      {isHi
                        ? 'कृपया पहले OCR सत्यापन कक्ष में जाकर पृष्ठों का सत्यापन पूर्ण करें।'
                        : 'Please complete page verification in scanner workspace first.'}
                    </p>
                  </>
                ) : (
                  <span>{isHi ? 'कोई पृष्ठ उपलब्ध नहीं है' : 'No pages available'}</span>
                )}
              </div>
            ) : (
              displayedLeftPages.map((page) => {
                const verified = isPageVerified(page);
                const isAlreadyAdded = includedPageIdSet.has(page.id);
                const isSelected = selectedPageIdsForAdd.includes(page.id);
                const snippet = getPageTextSnippet(page);
                const thumbUrl = getStorageUrl(page.preprocessed_image_path || page.original_image_path);

                return (
                  <div
                    key={page.id}
                    className={`p-3 rounded-2xl border transition-all duration-150 flex flex-col gap-2 ${
                      isAlreadyAdded
                        ? 'bg-emerald-50/40 border-emerald-200/60 opacity-90'
                        : isSelected
                        ? 'bg-amber-50/50 border-amber-300 shadow-2xs'
                        : 'bg-white border-stone-200/80 hover:border-stone-300'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2.5">
                      {/* Checkbox & Page Number */}
                      <div className="flex items-center gap-2 min-w-0">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          disabled={isAlreadyAdded || !verified}
                          onChange={() => handleTogglePageSelectForAdd(page.id)}
                          className="w-4 h-4 accent-vedic-700 rounded text-vedic-700 disabled:opacity-40 cursor-pointer"
                        />

                        {/* Thumbnail */}
                        <div className="w-10 h-10 rounded-lg bg-stone-100 border border-stone-200 overflow-hidden shrink-0 flex items-center justify-center">
                          {thumbUrl ? (
                            <img
                              src={thumbUrl}
                              alt={`P${page.page_number}`}
                              className="w-full h-full object-cover"
                              onError={(e) => {
                                e.currentTarget.style.display = 'none';
                              }}
                            />
                          ) : (
                            <FileText className="w-4 h-4 text-stone-400" />
                          )}
                        </div>

                        <div className="min-w-0">
                          <span className="font-devanagari font-bold text-xs sm:text-sm text-stone-900 block truncate">
                            {isHi ? `पृष्ठ ${page.page_number}` : `Page ${page.page_number}`}
                          </span>
                          <span className="text-[10px] text-stone-400 font-mono block">
                            क्रम: {page.upload_order || page.page_number}
                          </span>
                        </div>
                      </div>

                      {/* Status Badge */}
                      <div className="shrink-0">
                        {verified ? (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200 font-devanagari">
                            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                            {isHi ? 'सत्यापित' : 'Verified'}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-stone-100 text-stone-600 border border-stone-200 font-devanagari">
                            {isHi ? 'लंबित' : 'Pending'}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Text Preview Snippet */}
                    {snippet && (
                      <p className="text-[11px] text-stone-600 font-devanagari line-clamp-2 bg-[#fcfbfa] p-1.5 rounded-lg border border-stone-100/90">
                        {snippet}
                      </p>
                    )}

                    {/* Add to Book Button */}
                    <div className="pt-1 flex items-center justify-between">
                      {isAlreadyAdded ? (
                        <span className="text-[11px] font-bold text-emerald-700 font-devanagari inline-flex items-center gap-1">
                          <Check className="w-3.5 h-3.5 text-emerald-600" />
                          {isHi ? 'पुस्तक में जोड़ा गया ✓' : 'Added to book ✓'}
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleAddSinglePage(page)}
                          disabled={!verified || isAddingPages}
                          className="w-full inline-flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-stone-100 hover:bg-vedic-50 text-stone-800 hover:text-vedic-900 disabled:opacity-40 font-bold text-xs font-devanagari border border-stone-200/90 transition-colors"
                        >
                          <Plus className="w-3.5 h-3.5 text-vedic-700" />
                          <span>{isHi ? 'पुस्तक में जोड़ें' : 'Add to Book'}</span>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* ========================================================= */}
        {/* CENTER/RIGHT PANEL (70% -> col-span-12 lg:col-span-8): Combined Text Viewer */}
        {/* ========================================================= */}
        <div className="lg:col-span-8 bg-white rounded-3xl border border-stone-200/90 shadow-2xs p-4 sm:p-5 flex flex-col gap-4">
          {/* Center/Right Panel Top Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-stone-100">
            <div className="flex items-center gap-2.5">
              <BookOpen className="w-5 h-5 text-vedic-700" />
              <div>
                <h2 className="font-devanagari font-bold text-base sm:text-lg text-stone-900">
                  {isHi ? 'संयुक्त ग्रन्थ पाठ (Combined Book)' : 'Combined Book Text'}
                </h2>
                <span className="text-xs text-stone-500 font-devanagari">
                  {includedPages.length} {isHi ? 'पृष्ठ संकलित' : 'pages compiled'} |{' '}
                  {combinedText ? combinedText.split(/\s+/).filter(Boolean).length : 0}{' '}
                  {isHi ? 'शब्द' : 'words'}
                </span>
              </div>
            </div>

            {/* View Mode Switcher: Blocks vs Full Editor vs Split */}
            <div className="flex items-center bg-stone-100 p-1 rounded-2xl border border-stone-200 text-xs font-devanagari shrink-0">
              <button
                type="button"
                onClick={() => setActiveViewMode('blocks')}
                className={`px-3 py-1.5 rounded-xl font-bold transition-all ${
                  activeViewMode === 'blocks'
                    ? 'bg-white text-vedic-950 shadow-2xs'
                    : 'text-stone-600 hover:text-stone-900 font-medium'
                }`}
              >
                {isHi ? 'पृष्ठ ब्लॉक दृश्य' : 'Block View'}
              </button>
              <button
                type="button"
                onClick={() => setActiveViewMode('editor')}
                className={`px-3 py-1.5 rounded-xl font-bold transition-all ${
                  activeViewMode === 'editor'
                    ? 'bg-white text-vedic-950 shadow-2xs'
                    : 'text-stone-600 hover:text-stone-900 font-medium'
                }`}
              >
                {isHi ? 'पूर्ण सम्पादक' : 'Full Editor'}
              </button>
              <button
                type="button"
                onClick={() => setActiveViewMode('split')}
                className={`px-3 py-1.5 rounded-xl font-bold transition-all hidden sm:inline-block ${
                  activeViewMode === 'split'
                    ? 'bg-white text-vedic-950 shadow-2xs'
                    : 'text-stone-600 hover:text-stone-900 font-medium'
                }`}
              >
                {isHi ? 'संयुक्त दृश्य' : 'Split View'}
              </button>
            </div>
          </div>

          {/* Action Toolbar for Center/Right Panel */}
          <div className="flex flex-wrap items-center justify-between gap-2.5 p-3 rounded-2xl bg-[#faf8f5] border border-stone-200/70">
            {/* Left Actions: Selection for copy */}
            <div className="flex items-center gap-2 flex-wrap">
              <button
                type="button"
                onClick={handleSelectAllBlocksForCopy}
                disabled={includedPages.length === 0}
                className="text-xs text-stone-600 hover:text-stone-900 font-devanagari font-medium disabled:opacity-40"
              >
                {isHi ? 'सभी ब्लॉक चुनें' : 'Select All Blocks'}
              </button>
              <span className="text-stone-300">|</span>
              <button
                type="button"
                onClick={handleDeselectAllBlocksForCopy}
                disabled={selectedBlockIdsForCopy.length === 0}
                className="text-xs text-stone-600 hover:text-stone-900 font-devanagari font-medium disabled:opacity-40"
              >
                {isHi ? 'अचयनित' : 'Deselect'}
              </button>

              {/* Selected Pages Copy Button */}
              <button
                type="button"
                onClick={handleCopySelectedPages}
                disabled={selectedBlockIdsForCopy.length === 0}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-stone-300 bg-white hover:bg-stone-50 disabled:opacity-40 text-stone-800 font-semibold text-xs font-devanagari transition-colors shadow-2xs ml-1"
                title={isHi ? 'चयनित पृष्ठों का पाठ कॉपी करें' : 'Copy selected pages text'}
              >
                {copiedSelected ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-600" />
                    <span className="text-emerald-700 font-bold">{isHi ? 'कॉपी हुआ! ✓' : 'Copied! ✓'}</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5 text-stone-600" />
                    <span>
                      {isHi
                        ? `चयनित पृष्ठ कॉपी करें (${selectedBlockIdsForCopy.length})`
                        : `Copy Selected (${selectedBlockIdsForCopy.length})`}
                    </span>
                  </>
                )}
              </button>
            </div>

            {/* Right Action: Complete Book Text Copy Button */}
            <button
              type="button"
              onClick={handleCopyCompleteBook}
              disabled={!combinedText || combinedText.trim().length === 0}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-vedic-700 hover:bg-vedic-800 disabled:opacity-40 text-white font-bold text-xs sm:text-sm font-devanagari transition-colors shadow-2xs"
              title={isHi ? 'संपूर्ण पुस्तक का पाठ क्लिपबोर्ड पर कॉपी करें' : 'Copy complete book text'}
            >
              {copiedComplete ? (
                <>
                  <Check className="w-4 h-4 text-emerald-300" />
                  <span>{isHi ? 'प्रतिलिपि बनाई गई! ✓' : 'Copied to Clipboard! ✓'}</span>
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4 text-amber-200" />
                  <span>{isHi ? 'संपूर्ण पुस्तक कॉपी करें' : 'Copy Complete Book'}</span>
                </>
              )}
            </button>
          </div>

          {/* Center/Right Panel Content: Render View based on activeViewMode */}
          {includedPages.length === 0 ? (
            <div className="p-12 text-center bg-stone-50/60 rounded-3xl border border-dashed border-stone-300 my-4 flex flex-col items-center justify-center gap-3">
              <div className="w-14 h-14 rounded-2xl bg-stone-100 border border-stone-200 text-stone-400 flex items-center justify-center text-xl font-bold font-devanagari">
                ग्र
              </div>
              <h3 className="text-base font-bold text-stone-800 font-devanagari">
                {isHi ? 'संकलक में कोई पृष्ठ नहीं जोड़ा गया है' : 'No pages added to builder yet'}
              </h3>
              <p className="text-xs text-stone-500 font-devanagari max-w-sm">
                {isHi
                  ? 'बाएँ पैनल से सत्यापित पृष्ठ चुनें और "पुस्तक में जोड़ें" बटन दबाकर ग्रन्थ का संकलन प्रारंभ करें।'
                  : 'Select verified pages from the left panel and click "Add to Book" to start compiling.'}
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {/* 1. BLOCKS VIEW (Drag-and-Drop Sortable Page Blocks) */}
              {(activeViewMode === 'blocks' || activeViewMode === 'split') && (
                <div className="flex flex-col gap-3">
                  <div className="flex items-center justify-between text-xs font-devanagari text-stone-500 px-1">
                    <span>
                      {isHi
                        ? 'पृष्ठ क्रम बदलने के लिए ग्रिप हैंडल पकड़कर खींचें (Drag & Drop):'
                        : 'Drag handles to reorder page sequence:'}
                    </span>
                    {isUpdatingOrder && (
                      <span className="inline-flex items-center gap-1 text-vedic-700 font-semibold">
                        <RefreshCw className="w-3 h-3 animate-spin" />
                        {isHi ? 'क्रम अद्यतन हो रहा है...' : 'Updating order...'}
                      </span>
                    )}
                  </div>

                  <DndContext
                    sensors={sensors}
                    collisionDetection={closestCenter}
                    onDragEnd={handleDragEnd}
                  >
                    <SortableContext
                      items={includedPages.map((p) => p.id)}
                      strategy={verticalListSortingStrategy}
                    >
                      <div className="flex flex-col gap-3.5">
                        {includedPages.map((page, idx) => (
                          <React.Fragment key={page.id}>
                            <SortableBlock
                              page={page}
                              index={idx}
                              isSelectedForCopy={selectedBlockIdsForCopy.includes(page.id)}
                              onToggleSelectCopy={handleToggleSelectBlockForCopy}
                              onRemove={handleRemovePage}
                              onSingleCopy={handleSinglePageCopy}
                              isHi={isHi}
                            />
                            {/* Page Separator visual indication between blocks */}
                            {idx < includedPages.length - 1 && (
                              <div className="flex items-center justify-center my-0.5 text-stone-300 font-mono text-[10px] select-none">
                                <span className="border-t border-stone-200/80 flex-1" />
                                <span className="px-3 text-stone-400 font-devanagari font-semibold">
                                  {isHi ? 'विभाजक रेखा (Separator)' : 'Separator'}
                                </span>
                                <span className="border-t border-stone-200/80 flex-1" />
                              </div>
                            )}
                          </React.Fragment>
                        ))}
                      </div>
                    </SortableContext>
                  </DndContext>
                </div>
              )}

              {/* 2. FULL TEXT EDITOR VIEW (Manual Add/Edit with 5s Auto-Save) */}
              {(activeViewMode === 'editor' || activeViewMode === 'split') && (
                <div className="flex flex-col gap-2 pt-2">
                  <div className="flex items-center justify-between text-xs font-devanagari">
                    <div className="flex items-center gap-1.5 font-bold text-stone-800">
                      <FileText className="w-4 h-4 text-vedic-700" />
                      <span>{isHi ? 'सम्पूर्ण ग्रन्थ सम्पादक (Full Text Editor)' : 'Full Book Text Editor'}</span>
                    </div>
                    <span className="text-[11px] text-stone-500 font-mono">
                      {combinedText.length} वर्ण | {combinedText.split(/\s+/).filter(Boolean).length} शब्द
                    </span>
                  </div>

                  <p className="text-[11px] text-stone-500 font-devanagari">
                    {isHi
                      ? 'यहाँ आप सीधे पाठ में संशोधन, नए भजन, अध्याय शीर्षक अथवा भूमिका जोड़ सकते हैं। बदलाव स्वतः हर ५ सेकंड में सुरक्षित हो जाते हैं।'
                      : 'You can directly edit the combined book text, add chapter titles, hymns, or forewords. Auto-saves every 5 seconds.'}
                  </p>

                  <div className="relative rounded-2xl border border-stone-300 overflow-hidden shadow-inner bg-white">
                    <textarea
                      value={combinedText}
                      onChange={handleManualTextChange}
                      rows={activeViewMode === 'split' ? 14 : 22}
                      placeholder={isHi ? 'यहाँ ग्रन्थ का संकलित पाठ दिखाई देगा...' : 'Combined book text will appear here...'}
                      className="w-full p-4 font-devanagari text-xs sm:text-sm text-stone-900 leading-relaxed focus:outline-none resize-y selection:bg-amber-100 bg-[#faf8f5]"
                    />
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
