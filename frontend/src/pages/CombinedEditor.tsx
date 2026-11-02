import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
  ArrowLeft, BookOpen, Save, RefreshCw, CheckCircle2,
  Search, X, Copy, Check, History,
  Bold, AlignLeft, AlignCenter, AlignJustify,
  Sparkles, FolderOpen, Trash2
} from 'lucide-react';
import { api, getStorageUrl } from '../services/api';
import { copyToClipboard } from '../utils/clipboard';
import type {
  BookData,
  PageData,
  BookBuilderData,
  BuilderHistoryEntry,
  BuilderStageComparisonItem,
  BuilderDraftItem
} from '../types';
import type { Language } from '../i18n/translations';

interface CombinedEditorProps {
  bookId: string;
  lang?: Language;
  onNavigateBack?: () => void;
  onNavigateHome?: () => void;
}

type ViewMode = 'combined' | 'pagewise';
type HindiFont = 'noto' | 'mangal' | 'martel';
type LineSpacing = '1.2' | '1.5' | '1.8' | '2.0';
type TextAlign = 'left' | 'center' | 'justify';

export const CombinedEditor: React.FC<CombinedEditorProps> = ({
  bookId,
  lang = 'hi',
  onNavigateBack,
  onNavigateHome: _onNavigateHome
}) => {
  const isHi = lang === 'hi';

  // ---------------------------------------------------------
  // State: Book & Builder Data
  // ---------------------------------------------------------
  const [book, setBook] = useState<BookData | null>(null);
  const [builderData, setBuilderData] = useState<BookBuilderData | null>(null);
  void builderData;
  const [includedPages, setIncludedPages] = useState<PageData[]>([]);
  const [combinedText, setCombinedText] = useState<string>('');

  // ---------------------------------------------------------
  // State: Editor Controls & Typography
  // ---------------------------------------------------------
  const [viewMode, setViewMode] = useState<ViewMode>('combined');
  const [selectedFont, setSelectedFont] = useState<HindiFont>('noto');
  const [lineSpacing, setLineSpacing] = useState<LineSpacing>('1.8');
  const [fontSize, setFontSize] = useState<number>(16);
  const [textAlign, setTextAlign] = useState<TextAlign>('left');
  const [showPageBreaks, setShowPageBreaks] = useState<boolean>(true);

  // ---------------------------------------------------------
  // State: Find & Replace (Ctrl+F)
  // ---------------------------------------------------------
  const [isSearchOpen, setIsSearchOpen] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [replaceQuery, setReplaceQuery] = useState<string>('');
  const [searchMatchesCount, setSearchMatchesCount] = useState<number>(0);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // ---------------------------------------------------------
  // State: Auto-Save & Manual Save (every 3 seconds)
  // ---------------------------------------------------------
  const [isDirty, setIsDirty] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [lastSavedTime, setLastSavedTime] = useState<Date | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const textRef = useRef<string>(combinedText);
  textRef.current = combinedText;
  const isDirtyRef = useRef<boolean>(isDirty);
  isDirtyRef.current = isDirty;
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // ---------------------------------------------------------
  // State: Modals (Draft Management & History Comparison)
  // ---------------------------------------------------------
  const [isDraftsModalOpen, setIsDraftsModalOpen] = useState<boolean>(false);
  const [draftsList, setDraftsList] = useState<BuilderDraftItem[]>([]);
  const [newDraftName, setNewDraftName] = useState<string>('');

  const [isHistoryModalOpen, setIsHistoryModalOpen] = useState<boolean>(false);
  const [historyTab, setHistoryTab] = useState<'3way' | 'diffs'>('3way');
  const [historyEntries, setHistoryEntries] = useState<BuilderHistoryEntry[]>([]);
  const [stageComparison, setStageComparison] = useState<BuilderStageComparisonItem[]>([]);
  const [selectedHistoryPageId, setSelectedHistoryPageId] = useState<string>('');

  // Loading & Error State
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  void errorMessage;
  const [copiedSuccess, setCopiedSuccess] = useState<boolean>(false);

  // Show auto-dismissing toast
  const showToast = useCallback((msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage((prev) => (prev === msg ? null : prev));
    }, 3000);
  }, []);

  // ---------------------------------------------------------
  // Font Family Class Resolution
  // ---------------------------------------------------------
  const fontClass = useMemo(() => {
    switch (selectedFont) {
      case 'mangal':
        return 'font-devanagari font-sans';
      case 'martel':
        return 'font-traditional serif font-serif';
      case 'noto':
      default:
        return 'font-devanagari';
    }
  }, [selectedFont]);

  // ---------------------------------------------------------
  // 1. Initial Load: Fetch Book, Builder, and Pages
  // ---------------------------------------------------------
  const loadEditorData = useCallback(async () => {
    if (!bookId) return;
    try {
      setIsLoading(true);
      setErrorMessage(null);

      const [bookRes, builderRes] = await Promise.all([
        api.getBook(bookId),
        api.getBookBuilder(bookId)
      ]);

      setBook(bookRes.book);
      if (builderRes && builderRes.builder) {
        setBuilderData(builderRes.builder);
        setCombinedText(builderRes.builder.combined_text || '');
        setIsDirty(false);

        // Sort included pages according to page_order
        if (builderRes.pages && builderRes.pages.length > 0) {
          const pageOrder = builderRes.builder.page_order || [];
          const sorted = [...builderRes.pages].sort((a, b) => {
            const idxA = pageOrder.indexOf(a.page_number);
            const idxB = pageOrder.indexOf(b.page_number);
            if (idxA === -1 && idxB === -1) return a.page_number - b.page_number;
            if (idxA === -1) return 1;
            if (idxB === -1) return -1;
            return idxA - idxB;
          });
          setIncludedPages(sorted);
          if (sorted.length > 0) {
            setSelectedHistoryPageId(sorted[0].id);
          }
        }
      }
    } catch (err: any) {
      console.error('Failed to load combined editor data:', err);
      setErrorMessage(err.message || (isHi ? 'डेटा लोड करने में त्रुटि हुई।' : 'Failed to load data.'));
    } finally {
      setIsLoading(false);
    }
  }, [bookId, isHi]);

  useEffect(() => {
    loadEditorData();
  }, [loadEditorData]);

  // ---------------------------------------------------------
  // 2. Auto-Save every 3 seconds if dirty
  // ---------------------------------------------------------
  useEffect(() => {
    const timer = setInterval(async () => {
      if (isDirtyRef.current && bookId && textRef.current !== undefined) {
        try {
          setIsSaving(true);
          await api.builderCombinedEdit(
            bookId,
            textRef.current,
            '3s Auto-save from CombinedEditor'
          );
          setIsDirty(false);
          isDirtyRef.current = false;
          setLastSavedTime(new Date());
        } catch (err: any) {
          console.error('Auto-save error:', err);
        } finally {
          setIsSaving(false);
        }
      }
    }, 3000); // 3 seconds

    return () => clearInterval(timer);
  }, [bookId]);

  // ---------------------------------------------------------
  // 3. Manual Save Button
  // ---------------------------------------------------------
  const handleManualSave = async () => {
    if (!bookId) return;
    try {
      setIsSaving(true);
      await api.builderCombinedEdit(
        bookId,
        combinedText,
        'Manual save from CombinedEditor'
      );
      setIsDirty(false);
      isDirtyRef.current = false;
      setLastSavedTime(new Date());
      showToast(isHi ? 'बदलाव सफलतापूर्वक सुरक्षित किए गए! ✓' : 'Changes saved successfully! ✓');
    } catch (err: any) {
      alert((isHi ? 'सहेजने में त्रुटि: ' : 'Save failed: ') + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  // ---------------------------------------------------------
  // 4. Keyboard Shortcuts: Ctrl+F for Find & Replace
  // ---------------------------------------------------------
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
        e.preventDefault();
        setIsSearchOpen(true);
        setTimeout(() => searchInputRef.current?.focus(), 100);
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        handleManualSave();
      } else if (e.key === 'Escape' && isSearchOpen) {
        setIsSearchOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isSearchOpen, combinedText]);

  // Search matches count update
  useEffect(() => {
    if (!searchQuery.trim() || !combinedText) {
      setSearchMatchesCount(0);
      return;
    }
    try {
      const escaped = searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const matches = combinedText.match(new RegExp(escaped, 'gi'));
      setSearchMatchesCount(matches ? matches.length : 0);
    } catch {
      setSearchMatchesCount(0);
    }
  }, [searchQuery, combinedText]);

  // ---------------------------------------------------------
  // 5. Find & Replace Handlers
  // ---------------------------------------------------------
  const handleReplaceOnce = () => {
    if (!searchQuery) return;
    const idx = combinedText.indexOf(searchQuery);
    if (idx !== -1) {
      const nextText =
        combinedText.slice(0, idx) +
        replaceQuery +
        combinedText.slice(idx + searchQuery.length);
      setCombinedText(nextText);
      setIsDirty(true);
      showToast(isHi ? 'शब्द प्रतिस्थापित किया गया।' : 'Replaced occurrence.');
    }
  };

  const handleReplaceAll = () => {
    if (!searchQuery) return;
    const count = searchMatchesCount;
    const nextText = combinedText.split(searchQuery).join(replaceQuery);
    setCombinedText(nextText);
    setIsDirty(true);
    showToast(isHi ? `${count} शब्द प्रतिस्थापित किए गए! ✓` : `Replaced ${count} occurrences! ✓`);
  };

  // ---------------------------------------------------------
  // 6. Formatting Helpers: Bhajan Titles, Doha, Separator
  // ---------------------------------------------------------
  const insertFormatting = (prefix: string, suffix: string = '') => {
    const textarea = textareaRef.current;
    if (!textarea) {
      setCombinedText((prev) => prev + `\n${prefix}भजन शीर्षक${suffix}\n`);
      setIsDirty(true);
      return;
    }

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = combinedText.substring(start, end);

    const replacement = selected
      ? `${prefix}${selected}${suffix}`
      : `${prefix}भजन शीर्षक${suffix}`;

    const nextText =
      combinedText.substring(0, start) +
      replacement +
      combinedText.substring(end);

    setCombinedText(nextText);
    setIsDirty(true);

    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(
        start + prefix.length,
        start + replacement.length - suffix.length
      );
    }, 50);
  };

  const handleMakeTitleBold = () => {
    insertFormatting('\n**॥ ', ' ॥**\n');
  };

  const handleAddDohaBrackets = () => {
    insertFormatting('॥ ', ' ॥');
  };

  const handleAddPageSeparator = () => {
    insertFormatting('\n\n-------------------------\n\n');
  };

  // ---------------------------------------------------------
  // 7. Page-wise Editing Synchronization
  // ---------------------------------------------------------
  // Parse sections based on "Page X" pattern or separators
  const pageSections = useMemo(() => {
    if (!combinedText) return [];
    const parts = combinedText.split(/\n\s*-------------------------\s*\n/);
    return parts.map((part, i) => {
      // Find original page number if present in header
      const match = part.match(/^Page\s*(\d+)/i) || part.match(/पृष्ठ\s*(\d+)/i);
      const matchedNum = match ? parseInt(match[1], 10) : (includedPages[i]?.page_number || i + 1);
      const matchingPageData = includedPages.find((p) => p.page_number === matchedNum) || includedPages[i];

      return {
        index: i,
        pageNumber: matchedNum,
        pageData: matchingPageData,
        text: part
      };
    });
  }, [combinedText, includedPages]);

  const handleUpdatePageSectionText = (sectionIndex: number, newSectionText: string) => {
    const parts = combinedText.split(/\n\s*-------------------------\s*\n/);
    if (sectionIndex >= 0 && sectionIndex < parts.length) {
      parts[sectionIndex] = newSectionText;
      const updatedCombined = parts.join('\n\n-------------------------\n\n');
      setCombinedText(updatedCombined);
      setIsDirty(true);
    }
  };

  // ---------------------------------------------------------
  // 8. Drafts Management Handlers
  // ---------------------------------------------------------
  const handleOpenDraftsModal = async () => {
    if (!bookId) return;
    try {
      const res = await api.listBuilderDrafts(bookId);
      setDraftsList(res.drafts || []);
      setIsDraftsModalOpen(true);
    } catch (e) {
      console.error(e);
      setIsDraftsModalOpen(true);
    }
  };

  const handleSaveNamedDraft = async () => {
    if (!bookId || !newDraftName.trim()) {
      alert(isHi ? 'कृपया ड्राफ्ट का नाम दर्ज करें।' : 'Please enter draft name.');
      return;
    }
    try {
      const res = await api.saveBuilderDraft(bookId, newDraftName.trim(), combinedText);
      setDraftsList([res.draft, ...draftsList]);
      setNewDraftName('');
      showToast(isHi ? 'नया ड्राफ्ट सहेजा गया! ✓' : 'Draft saved! ✓');
    } catch (err: any) {
      alert('ड्राफ्ट सहेजने में विफल: ' + err.message);
    }
  };

  const handleLoadDraft = async (draftId: string) => {
    if (!bookId) return;
    const confirm = window.confirm(
      isHi
        ? 'क्या आप इस ड्राफ्ट को लोड करना चाहते हैं? वर्तमान असहेजे बदलाव बदल दिए जाएंगे।'
        : 'Load this draft? Current unsaved edits will be replaced.'
    );
    if (!confirm) return;

    try {
      const res = await api.loadBuilderDraft(bookId, draftId);
      if (res && res.draft) {
        setCombinedText(res.draft.combined_text || '');
        setIsDirty(false);
        setIsDraftsModalOpen(false);
        showToast(isHi ? `ड्राफ्ट '${res.draft.name}' लोड किया गया! ✓` : 'Draft loaded! ✓');
      }
    } catch (err: any) {
      alert('ड्राफ्ट लोड करने में त्रुटि: ' + err.message);
    }
  };

  const handleDeleteDraft = async (draftId: string) => {
    if (!bookId) return;
    if (!window.confirm(isHi ? 'क्या आप इस ड्राफ्ट को हटाना चाहते हैं?' : 'Delete this draft?')) return;
    try {
      await api.deleteBuilderDraft(bookId, draftId);
      setDraftsList(draftsList.filter((d) => d.id !== draftId));
      showToast(isHi ? 'ड्राफ्ट हटा दिया गया।' : 'Draft deleted.');
    } catch (err: any) {
      alert('हटाने में त्रुटि: ' + err.message);
    }
  };

  // ---------------------------------------------------------
  // 9. History & 3-Way Comparison Handlers
  // ---------------------------------------------------------
  const handleOpenHistoryModal = async () => {
    if (!bookId) return;
    try {
      const [histRes, compRes] = await Promise.all([
        api.getBuilderHistory(bookId),
        api.getBuilderStageComparison(bookId)
      ]);
      setHistoryEntries(histRes.history || []);
      setStageComparison(compRes.comparison || []);
      setIsHistoryModalOpen(true);
    } catch (e) {
      console.error(e);
      setIsHistoryModalOpen(true);
    }
  };

  // Copy complete text
  const handleCopyComplete = async () => {
    try {
      await copyToClipboard(combinedText);
      setCopiedSuccess(true);
      showToast(isHi ? 'संपूर्ण पाठ क्लिपबोर्ड पर कॉपी किया गया! ✓' : 'Copied to clipboard! ✓');
      setTimeout(() => setCopiedSuccess(false), 2000);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="flex-1 max-w-7xl w-full mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 flex flex-col gap-4 font-sans text-stone-900">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-3 bg-vedic-950 text-white rounded-2xl shadow-xl border border-vedic-800 flex items-center gap-2.5 font-devanagari text-xs sm:text-sm animate-in fade-in slide-in-from-bottom-3 duration-200">
          <Sparkles className="w-4 h-4 text-amber-400 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Top Navigation & Status Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-4 rounded-3xl bg-white border border-stone-200/90 shadow-2xs">
        <div className="flex items-center gap-3">
          {onNavigateBack && (
            <button
              type="button"
              onClick={onNavigateBack}
              className="p-2 rounded-xl border border-stone-200 hover:bg-stone-50 text-stone-700 transition-colors shadow-2xs shrink-0"
              title={isHi ? 'संकलक पर वापस' : 'Back to Builder'}
            >
              <ArrowLeft className="w-4 h-4 text-vedic-700" />
            </button>
          )}

          <div className="w-10 h-10 rounded-2xl bg-amber-50 border border-amber-200 text-amber-800 flex items-center justify-center shrink-0">
            <BookOpen className="w-5 h-5 text-vedic-700" />
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base sm:text-lg font-bold text-stone-900 font-devanagari">
                {book?.name || (isHi ? 'संयुक्त पाण्डुलिपि सम्पादक' : 'Combined Book Editor')}
              </h1>
              <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-vedic-100 text-vedic-800 font-devanagari">
                {includedPages.length} {isHi ? 'पृष्ठ' : 'pages'}
              </span>
            </div>
            <p className="text-xs text-stone-500 font-devanagari">
              {isHi
                ? 'ग्रन्थ पाठ सम्पादन, शीर्षक अलंकरण एवं ३-चरणीय पाण्डुलिपि इतिहास'
                : 'Devanagari manuscript editing, heading formatting & 3-stage history review'}
            </p>
          </div>
        </div>

        {/* Action Controls & Auto-Save Indicator */}
        <div className="flex items-center gap-2 flex-wrap justify-end">
          {/* Status Indicator */}
          <div className="flex items-center gap-1.5 text-[11px] font-devanagari text-stone-500 bg-stone-50 px-2.5 py-1.5 rounded-xl border border-stone-200">
            {isSaving ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-vedic-600" />
                <span className="text-vedic-700 font-medium">{isHi ? 'सहेजा जा रहा है...' : 'Saving...'}</span>
              </>
            ) : isDirty ? (
              <>
                <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                <span className="text-amber-800 font-semibold">{isHi ? 'असंरक्षित बदलाव' : 'Unsaved edits'}</span>
              </>
            ) : lastSavedTime ? (
              <>
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                <span>
                  {isHi ? 'सुरक्षित' : 'Saved'}{' '}
                  {lastSavedTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </>
            ) : (
              <span className="text-stone-400">3s {isHi ? 'स्वतः सहेजें' : 'Auto-save'}</span>
            )}
          </div>

          {/* Drafts Manager Button */}
          <button
            type="button"
            onClick={handleOpenDraftsModal}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-stone-200 hover:bg-stone-50 text-stone-700 text-xs font-semibold font-devanagari shadow-2xs transition-colors"
            title={isHi ? 'ड्राफ्ट्स प्रबन्धन' : 'Drafts Management'}
          >
            <FolderOpen className="w-3.5 h-3.5 text-amber-600" />
            <span>{isHi ? 'ड्राफ्ट्स' : 'Drafts'}</span>
          </button>

          {/* History & 3-Way Comparison Button */}
          <button
            type="button"
            onClick={handleOpenHistoryModal}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-stone-200 hover:bg-stone-50 text-stone-700 text-xs font-semibold font-devanagari shadow-2xs transition-colors"
            title={isHi ? 'मूल OCR vs सत्यापित vs संयुक्त इतिहास' : 'History: Original OCR vs Verified vs Combined'}
          >
            <History className="w-3.5 h-3.5 text-indigo-600" />
            <span>{isHi ? 'इतिहास व तुलना' : 'History & Diff'}</span>
          </button>

          {/* Manual Save Button */}
          <button
            type="button"
            onClick={handleManualSave}
            disabled={isSaving || !isDirty}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-vedic-700 hover:bg-vedic-800 disabled:opacity-40 text-white text-xs font-bold font-devanagari shadow-2xs transition-colors"
          >
            <Save className="w-3.5 h-3.5" />
            <span>{isHi ? 'ड्राफ्ट सहेजें' : 'Save Draft'}</span>
          </button>
        </div>
      </div>

      {/* Editor Controls & Typography Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-white rounded-2xl border border-stone-200/90 shadow-2xs">
        {/* Left Side: View Toggle & Formatting Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* View Mode Toggle: Combined vs Page-wise */}
          <div className="flex items-center bg-stone-100 p-1 rounded-xl border border-stone-200 text-xs font-devanagari">
            <button
              type="button"
              onClick={() => setViewMode('combined')}
              className={`px-3 py-1 rounded-lg font-bold transition-all ${
                viewMode === 'combined'
                  ? 'bg-white text-vedic-950 shadow-2xs'
                  : 'text-stone-600 hover:text-stone-900 font-medium'
              }`}
            >
              {isHi ? 'संयुक्त पाण्डुलिपि' : 'Combined Doc'}
            </button>
            <button
              type="button"
              onClick={() => setViewMode('pagewise')}
              className={`px-3 py-1 rounded-lg font-bold transition-all ${
                viewMode === 'pagewise'
                  ? 'bg-white text-vedic-950 shadow-2xs'
                  : 'text-stone-600 hover:text-stone-900 font-medium'
              }`}
            >
              {isHi ? 'पृष्ठ-वार सम्पादन' : 'Page-wise'}
            </button>
          </div>

          <div className="h-5 w-px bg-stone-200 hidden sm:block" />

          {/* Heading Formatting (Bhajan Title Bold) */}
          <button
            type="button"
            onClick={handleMakeTitleBold}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-stone-200 bg-stone-50 hover:bg-stone-100 text-stone-800 text-xs font-devanagari font-bold shadow-2xs"
            title={isHi ? 'भजन शीर्षक को बोल्ड करें (**॥ शीर्षक ॥**)' : 'Format Bhajan Title'}
          >
            <Bold className="w-3.5 h-3.5 text-vedic-700" />
            <span>{isHi ? 'भजन शीर्षक' : 'Bhajan Title'}</span>
          </button>

          {/* Doha Brackets */}
          <button
            type="button"
            onClick={handleAddDohaBrackets}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-stone-200 bg-stone-50 hover:bg-stone-100 text-stone-800 text-xs font-devanagari shadow-2xs"
            title={isHi ? 'दोहा / पद कोष्ठक जोड़ें (॥ ... ॥)' : 'Doha/Chaupai brackets'}
          >
            <span>॥ दोहा ॥</span>
          </button>

          {/* Insert Page Separator */}
          <button
            type="button"
            onClick={handleAddPageSeparator}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-stone-200 bg-stone-50 hover:bg-stone-100 text-stone-800 text-xs font-devanagari shadow-2xs"
            title={isHi ? 'पृष्ठ विभाजक जोड़ें' : 'Insert page separator'}
          >
            <span>विभाजक रेखा</span>
          </button>

          {/* Toggle Page Breaks Visual */}
          <label className="flex items-center gap-1.5 text-xs font-devanagari text-stone-600 cursor-pointer ml-1 select-none">
            <input
              type="checkbox"
              checked={showPageBreaks}
              onChange={(e) => setShowPageBreaks(e.target.checked)}
              className="w-3.5 h-3.5 accent-vedic-700 rounded cursor-pointer"
            />
            <span>{isHi ? 'पृष्ठ-विच्छेद दिखाएं' : 'Page breaks'}</span>
          </label>
        </div>

        {/* Right Side: Font Selector, Line Spacing, Search Button */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Hindi Font Selection Dropdown */}
          <div className="flex items-center gap-1 bg-stone-50 p-1 rounded-xl border border-stone-200 text-xs font-devanagari">
            <span className="text-[11px] text-stone-500 pl-1">{isHi ? 'फ़ॉन्ट:' : 'Font:'}</span>
            <select
              value={selectedFont}
              onChange={(e) => setSelectedFont(e.target.value as HindiFont)}
              className="bg-transparent font-bold text-stone-900 focus:outline-none cursor-pointer pr-1"
            >
              <option value="noto">Noto Sans Devanagari</option>
              <option value="mangal">Mangal (पारंपरिक)</option>
              <option value="martel">Martel (शास्त्रीय सेरिफ़)</option>
            </select>
          </div>

          {/* Line Spacing Control */}
          <div className="flex items-center gap-1 bg-stone-50 p-1 rounded-xl border border-stone-200 text-xs font-devanagari">
            <span className="text-[11px] text-stone-500 pl-1">{isHi ? 'दूरी:' : 'Spacing:'}</span>
            <select
              value={lineSpacing}
              onChange={(e) => setLineSpacing(e.target.value as LineSpacing)}
              className="bg-transparent font-bold text-stone-900 focus:outline-none cursor-pointer pr-1"
            >
              <option value="1.2">1.2x (संक्षिप्त)</option>
              <option value="1.5">1.5x (मानक)</option>
              <option value="1.8">1.8x (विस्तृत)</option>
              <option value="2.0">2.0x (द्विगुण)</option>
            </select>
          </div>

          {/* Text Alignment */}
          <div className="flex items-center bg-stone-100 p-0.5 rounded-xl border border-stone-200">
            <button
              type="button"
              onClick={() => setTextAlign('left')}
              className={`p-1.5 rounded-lg ${textAlign === 'left' ? 'bg-white shadow-2xs text-vedic-700' : 'text-stone-500'}`}
              title="Left align"
            >
              <AlignLeft className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setTextAlign('center')}
              className={`p-1.5 rounded-lg ${textAlign === 'center' ? 'bg-white shadow-2xs text-vedic-700' : 'text-stone-500'}`}
              title="Center align"
            >
              <AlignCenter className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setTextAlign('justify')}
              className={`p-1.5 rounded-lg ${textAlign === 'justify' ? 'bg-white shadow-2xs text-vedic-700' : 'text-stone-500'}`}
              title="Justify align"
            >
              <AlignJustify className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Font Size Controls */}
          <div className="flex items-center gap-1 bg-stone-50 p-1 rounded-xl border border-stone-200 text-xs font-devanagari">
            <button
              type="button"
              onClick={() => setFontSize(Math.max(12, fontSize - 1))}
              className="px-2 py-0.5 rounded bg-white hover:bg-stone-100 border border-stone-200 font-bold text-stone-700"
              title="फ़ॉन्ट छोटा करें"
            >
              A-
            </button>
            <span className="text-[11px] font-mono px-1">{fontSize}px</span>
            <button
              type="button"
              onClick={() => setFontSize(Math.min(28, fontSize + 1))}
              className="px-2 py-0.5 rounded bg-white hover:bg-stone-100 border border-stone-200 font-bold text-stone-700"
              title="फ़ॉन्ट बड़ा करें"
            >
              A+
            </button>
          </div>

          {/* Find & Replace Trigger Button */}
          <button
            type="button"
            onClick={() => setIsSearchOpen(!isSearchOpen)}
            className={`p-1.5 rounded-xl border transition-colors shadow-2xs ${
              isSearchOpen
                ? 'bg-vedic-50 border-vedic-300 text-vedic-800'
                : 'border-stone-200 bg-white hover:bg-stone-50 text-stone-700'
            }`}
            title="खोजें और बदलें (Ctrl+F)"
          >
            <Search className="w-4 h-4" />
          </button>

          {/* Copy Complete Text Button */}
          <button
            type="button"
            onClick={handleCopyComplete}
            className="p-1.5 rounded-xl border border-stone-200 bg-white hover:bg-stone-50 text-stone-700 transition-colors shadow-2xs"
            title={isHi ? 'संपूर्ण पाठ कॉपी करें' : 'Copy complete text'}
          >
            {copiedSuccess ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4 text-stone-600" />}
          </button>
        </div>
      </div>

      {/* Find & Replace Toolbar (Expandable / Ctrl+F) */}
      {isSearchOpen && (
        <div className="p-3.5 rounded-2xl bg-amber-50/70 border border-amber-200/90 shadow-2xs flex flex-wrap items-center justify-between gap-3 text-xs font-devanagari animate-in fade-in duration-150">
          <div className="flex items-center gap-2.5 flex-wrap flex-1 min-w-[280px]">
            {/* Search Input */}
            <div className="relative flex-1 min-w-[180px]">
              <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={isHi ? 'खोजें (Search text)...' : 'Find in text...'}
                className="w-full pl-8 pr-3 py-1.5 rounded-xl border border-amber-300 bg-white focus:outline-none focus:ring-1 focus:ring-amber-400"
              />
            </div>

            {/* Replace Input */}
            <div className="relative flex-1 min-w-[180px]">
              <input
                type="text"
                value={replaceQuery}
                onChange={(e) => setReplaceQuery(e.target.value)}
                placeholder={isHi ? 'इससे बदलें (Replace with)...' : 'Replace with...'}
                className="w-full px-3 py-1.5 rounded-xl border border-amber-300 bg-white focus:outline-none focus:ring-1 focus:ring-amber-400"
              />
            </div>

            {/* Match Counter Badge */}
            <span className="text-[11px] font-mono px-2 py-1 rounded-lg bg-white border border-amber-200 text-stone-700 shrink-0">
              {searchMatchesCount} {isHi ? 'मिले' : 'matches'}
            </span>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <button
              type="button"
              onClick={handleReplaceOnce}
              disabled={!searchQuery || searchMatchesCount === 0}
              className="px-3 py-1.5 rounded-xl border border-amber-300 bg-white hover:bg-amber-100 disabled:opacity-40 font-bold text-stone-800 shadow-2xs"
            >
              {isHi ? 'बदलें' : 'Replace'}
            </button>
            <button
              type="button"
              onClick={handleReplaceAll}
              disabled={!searchQuery || searchMatchesCount === 0}
              className="px-3 py-1.5 rounded-xl bg-vedic-700 hover:bg-vedic-800 disabled:opacity-40 text-white font-bold shadow-2xs"
            >
              {isHi ? 'सभी बदलें' : 'Replace All'}
            </button>
            <button
              type="button"
              onClick={() => setIsSearchOpen(false)}
              className="p-1 rounded-lg text-stone-400 hover:text-stone-700 ml-1"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Main Document Workspace */}
      <div className="bg-[#f7f5f0] p-4 sm:p-8 rounded-3xl border border-stone-200/90 shadow-inner min-h-[600px] flex justify-center">
        {isLoading ? (
          <div className="p-12 text-center font-devanagari text-xs text-stone-500 flex flex-col items-center justify-center gap-2">
            <RefreshCw className="w-6 h-6 animate-spin text-vedic-700" />
            <span>{isHi ? 'ग्रन्थ पाठ लोड हो रहा है...' : 'Loading document...'}</span>
          </div>
        ) : viewMode === 'combined' ? (
          /* ========================================================= */
          /* 1. CONTINUOUS MANUSCRIPT DOCUMENT VIEW                    */
          /* ========================================================= */
          <div className="w-full max-w-4xl bg-white rounded-2xl shadow-md border border-stone-200/90 p-6 sm:p-10 flex flex-col gap-6">
            {/* Manuscript Header Banner */}
            <div className="text-center pb-6 border-b border-stone-200/70 select-none">
              <span className="text-xs font-traditional font-bold text-amber-800 tracking-widest block mb-1">
                ॥ ॐ श्री परमात्मने नमः ॥
              </span>
              <h2 className="text-xl sm:text-2xl font-bold font-devanagari text-stone-900">
                {book?.name || 'धार्मिक ग्रन्थ संकलन'}
              </h2>
              <span className="text-xs text-stone-500 font-devanagari block mt-1">
                {includedPages.length} {isHi ? 'सत्यापित पृष्ठों का एकीकृत संस्करण' : 'verified pages unified edition'}
              </span>
            </div>

            {/* Continuous Textarea with Devanagari Typography */}
            <div className="relative">
              <textarea
                ref={textareaRef}
                value={combinedText}
                onChange={(e) => {
                  setCombinedText(e.target.value);
                  setIsDirty(true);
                }}
                rows={28}
                style={{
                  lineHeight: lineSpacing,
                  fontSize: `${fontSize}px`,
                  textAlign: textAlign
                }}
                className={`w-full p-2 bg-transparent border-0 focus:outline-none resize-y selection:bg-amber-100 ${fontClass} text-stone-900 leading-relaxed`}
                placeholder={isHi ? 'यहाँ सम्पूर्ण ग्रन्थ का पाठ दिखाई देगा...' : 'Document text...'}
              />
            </div>

            {/* Document Footer */}
            <div className="pt-6 border-t border-stone-200/70 flex items-center justify-between text-xs text-stone-500 font-devanagari select-none">
              <span>
                {combinedText.split(/\s+/).filter(Boolean).length} {isHi ? 'शब्द' : 'words'} | {combinedText.length}{' '}
                {isHi ? 'वर्ण' : 'chars'}
              </span>
              <span>वाणीसंशोधक हेरिटेज संस्करण</span>
            </div>
          </div>
        ) : (
          /* ========================================================= */
          /* 2. PAGE-BY-PAGE SECTIONED EDITING VIEW                    */
          /* ========================================================= */
          <div className="w-full max-w-4xl flex flex-col gap-6">
            {pageSections.length === 0 ? (
              <div className="p-8 text-center bg-white rounded-2xl border border-stone-200 text-stone-500 font-devanagari text-xs">
                {isHi ? 'कोई पृष्ठ अनुभाग नहीं मिला।' : 'No page sections found.'}
              </div>
            ) : (
              pageSections.map((sec, idx) => {
                const thumb = sec.pageData
                  ? getStorageUrl(sec.pageData.preprocessed_image_path || sec.pageData.original_image_path)
                  : '';

                return (
                  <div
                    key={`page-sec-${idx}`}
                    className="bg-white rounded-2xl border border-stone-200/90 shadow-2xs overflow-hidden flex flex-col"
                  >
                    {/* Page Section Header with Original Page Number */}
                    <div className="flex items-center justify-between px-4 py-3 bg-stone-50 border-b border-stone-200/80 gap-3">
                      <div className="flex items-center gap-2.5">
                        {thumb && (
                          <div className="w-8 h-8 rounded-lg bg-stone-100 border border-stone-200 overflow-hidden shrink-0">
                            <img
                              src={thumb}
                              alt={`P${sec.pageNumber}`}
                              className="w-full h-full object-cover"
                              onError={(e) => {
                                e.currentTarget.style.display = 'none';
                              }}
                            />
                          </div>
                        )}
                        <div>
                          <span className="font-devanagari font-bold text-xs sm:text-sm text-stone-900 block">
                            {isHi ? `मूल पृष्ठ ${sec.pageNumber}` : `Original Page ${sec.pageNumber}`}
                          </span>
                          <span className="text-[10px] text-stone-400 font-mono block">
                            अनुभाग #{idx + 1}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="text-[11px] text-stone-500 font-devanagari">
                          {sec.text.split(/\s+/).filter(Boolean).length} {isHi ? 'शब्द' : 'words'}
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            copyToClipboard(sec.text);
                            showToast(isHi ? `पृष्ठ ${sec.pageNumber} कॉपी हुआ!` : 'Page text copied!');
                          }}
                          className="p-1 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-100"
                          title="इस पृष्ठ का पाठ कॉपी करें"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* Page Text Area */}
                    <div className="p-4 bg-white">
                      <textarea
                        value={sec.text}
                        onChange={(e) => handleUpdatePageSectionText(idx, e.target.value)}
                        rows={10}
                        style={{
                          lineHeight: lineSpacing,
                          fontSize: `${fontSize}px`,
                          textAlign: textAlign
                        }}
                        className={`w-full p-3 rounded-xl bg-[#faf8f5] border border-stone-200/80 focus:outline-none focus:border-vedic-500 resize-y ${fontClass} text-stone-900 leading-relaxed`}
                      />
                    </div>

                    {/* Visible Page Break Indicator */}
                    {showPageBreaks && idx < pageSections.length - 1 && (
                      <div className="px-4 py-2 bg-amber-50/50 border-t border-dashed border-amber-300 text-center text-[11px] font-devanagari text-amber-800 select-none flex items-center justify-center gap-2">
                        <span className="border-t border-amber-300 flex-1" />
                        <span>── {isHi ? `पृष्ठ ${sec.pageNumber + 1} विच्छेद (Page Break)` : 'Page Break'} ──</span>
                        <span className="border-t border-amber-300 flex-1" />
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>

      {/* ========================================================= */}
      {/* MODAL 1: DRAFTS MANAGEMENT                                */}
      {/* ========================================================= */}
      {isDraftsModalOpen && (
        <div className="fixed inset-0 z-50 bg-stone-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white w-full max-w-xl rounded-3xl shadow-2xl border border-stone-200 overflow-hidden flex flex-col max-h-[85vh]">
            <div className="flex items-center justify-between p-4 border-b border-stone-100">
              <div className="flex items-center gap-2">
                <FolderOpen className="w-5 h-5 text-amber-600" />
                <h3 className="font-devanagari font-bold text-base text-stone-900">
                  {isHi ? 'ड्राफ्ट्स प्रबन्धन (Draft Management)' : 'Draft Management'}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setIsDraftsModalOpen(false)}
                className="p-1 rounded-lg text-stone-400 hover:text-stone-700"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 flex flex-col gap-4 overflow-y-auto">
              {/* Save New Draft Input */}
              <div className="p-3 rounded-2xl bg-stone-50 border border-stone-200 flex flex-col gap-2">
                <span className="text-xs font-bold text-stone-800 font-devanagari">
                  {isHi ? 'वर्तमान पाठ को नया ड्राफ्ट नाम दें:' : 'Save Current Edits as Named Draft:'}
                </span>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={newDraftName}
                    onChange={(e) => setNewDraftName(e.target.value)}
                    placeholder={isHi ? 'उदा. भजन १-५० शुद्धिकरण...' : 'Draft title...'}
                    className="flex-1 px-3 py-1.5 rounded-xl border border-stone-300 text-xs font-devanagari focus:outline-none focus:border-vedic-500 bg-white"
                  />
                  <button
                    type="button"
                    onClick={handleSaveNamedDraft}
                    className="px-4 py-1.5 rounded-xl bg-vedic-700 hover:bg-vedic-800 text-white font-bold text-xs font-devanagari shadow-2xs"
                  >
                    {isHi ? 'सहेजें' : 'Save'}
                  </button>
                </div>
              </div>

              {/* Saved Drafts List */}
              <div className="flex flex-col gap-2">
                <span className="text-xs font-bold text-stone-800 font-devanagari">
                  {isHi ? 'सहेजे गए ड्राफ्ट्स:' : 'Saved Drafts:'}
                </span>
                {draftsList.length === 0 ? (
                  <p className="text-xs text-stone-400 font-devanagari text-center py-6">
                    {isHi ? 'कोई सहेजा गया ड्राफ्ट उपलब्ध नहीं है।' : 'No saved drafts yet.'}
                  </p>
                ) : (
                  draftsList.map((draft) => (
                    <div
                      key={draft.id}
                      className="p-3 rounded-xl border border-stone-200/90 bg-white flex items-center justify-between gap-3 shadow-2xs"
                    >
                      <div>
                        <span className="font-devanagari font-bold text-xs sm:text-sm text-stone-900 block">
                          {draft.name}
                        </span>
                        <span className="text-[10px] text-stone-400 font-mono block">
                          {draft.word_count} शब्द | {new Date(draft.created_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => handleLoadDraft(draft.id)}
                          className="px-2.5 py-1 rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-300 text-xs font-devanagari font-bold shadow-2xs"
                        >
                          {isHi ? 'लोड करें' : 'Load'}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteDraft(draft.id)}
                          className="p-1 rounded-lg text-rose-500 hover:bg-rose-50 hover:text-rose-700"
                          title="हटाएं"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* MODAL 2: HISTORY (Original OCR vs Verified vs Combined)   */}
      {/* ========================================================= */}
      {isHistoryModalOpen && (
        <div className="fixed inset-0 z-50 bg-stone-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white w-full max-w-5xl rounded-3xl shadow-2xl border border-stone-200 overflow-hidden flex flex-col max-h-[90vh]">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-stone-100">
              <div className="flex items-center gap-2">
                <History className="w-5 h-5 text-indigo-600" />
                <h3 className="font-devanagari font-bold text-base text-stone-900">
                  {isHi ? 'पाण्डुलिपि संशोधन इतिहास व तुलना' : 'Manuscript Edit History & Stage Diff'}
                </h3>
              </div>

              {/* Tab Switcher: 3-Way Stage Comparison vs Edit Diffs */}
              <div className="flex items-center bg-stone-100 p-1 rounded-xl border border-stone-200 text-xs font-devanagari">
                <button
                  type="button"
                  onClick={() => setHistoryTab('3way')}
                  className={`px-3 py-1 rounded-lg font-bold transition-all ${
                    historyTab === '3way' ? 'bg-white text-vedic-950 shadow-2xs' : 'text-stone-600'
                  }`}
                >
                  {isHi ? '३-चरणीय तुलना' : '3-Stage Comparison'}
                </button>
                <button
                  type="button"
                  onClick={() => setHistoryTab('diffs')}
                  className={`px-3 py-1 rounded-lg font-bold transition-all ${
                    historyTab === 'diffs' ? 'bg-white text-vedic-950 shadow-2xs' : 'text-stone-600'
                  }`}
                >
                  {isHi ? 'संशोधन इतिहास' : 'Edit Log Diffs'}
                </button>
              </div>

              <button
                type="button"
                onClick={() => setIsHistoryModalOpen(false)}
                className="p-1 rounded-lg text-stone-400 hover:text-stone-700"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-4 sm:p-6 overflow-y-auto flex-1 flex flex-col gap-4">
              {historyTab === '3way' ? (
                /* TAB 1: 3-WAY STAGE COMPARISON (Original OCR -> Verified -> Combined) */
                <div className="flex flex-col gap-4">
                  {/* Page Selector for Comparison */}
                  {stageComparison.length > 0 && (
                    <div className="flex items-center gap-2 text-xs font-devanagari">
                      <span className="font-bold text-stone-700">{isHi ? 'पृष्ठ चुनें:' : 'Select Page:'}</span>
                      <select
                        value={selectedHistoryPageId}
                        onChange={(e) => setSelectedHistoryPageId(e.target.value)}
                        className="bg-stone-50 border border-stone-300 rounded-xl px-3 py-1.5 text-stone-900 font-bold focus:outline-none"
                      >
                        {stageComparison.map((p) => (
                          <option key={p.page_id} value={p.page_id}>
                            पृष्ठ {p.page_number} (क्रम: {p.upload_order})
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {(() => {
                    const activeComp =
                      stageComparison.find((p) => p.page_id === selectedHistoryPageId) || stageComparison[0];

                    if (!activeComp) {
                      return (
                        <p className="text-xs text-stone-400 font-devanagari text-center py-8">
                          {isHi ? 'कोई तुलनात्मक डेटा उपलब्ध नहीं है।' : 'No comparison data available.'}
                        </p>
                      );
                    }

                    // Find corresponding slice in combined text
                    const currentSlice =
                      pageSections.find((s) => s.pageNumber === activeComp.page_number)?.text || '';

                    return (
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {/* 1. Original OCR Column */}
                        <div className="flex flex-col gap-2 p-3.5 rounded-2xl bg-stone-50 border border-stone-200">
                          <span className="text-xs font-bold text-stone-700 font-devanagari flex items-center justify-between">
                            <span>१. मूल OCR (Raw Scan)</span>
                            <span className="text-[10px] text-stone-400">चरण १</span>
                          </span>
                          <div className="p-3 bg-white rounded-xl border border-stone-200/90 text-xs font-devanagari text-stone-700 leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto">
                            {activeComp.raw_ocr_text || (
                              <span className="text-stone-400 italic font-devanagari">
                                {isHi ? '(मूल OCR पाठ अनुपलब्ध)' : '(No raw OCR text)'}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* 2. Verified Text Column */}
                        <div className="flex flex-col gap-2 p-3.5 rounded-2xl bg-emerald-50/60 border border-emerald-200">
                          <span className="text-xs font-bold text-emerald-900 font-devanagari flex items-center justify-between">
                            <span>२. सत्यापित पाठ (Verified)</span>
                            <span className="text-[10px] text-emerald-600 font-bold">चरण ४ ✓</span>
                          </span>
                          <div className="p-3 bg-white rounded-xl border border-emerald-200/90 text-xs font-devanagari text-stone-800 leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto">
                            {activeComp.verified_text || (
                              <span className="text-stone-400 italic font-devanagari">
                                {isHi ? '(सत्यापित पाठ अनुपलब्ध)' : '(No verified text)'}
                              </span>
                            )}
                          </div>
                        </div>

                        {/* 3. Current Combined Text Column */}
                        <div className="flex flex-col gap-2 p-3.5 rounded-2xl bg-amber-50/60 border border-amber-200">
                          <span className="text-xs font-bold text-amber-950 font-devanagari flex items-center justify-between">
                            <span>३. संयुक्त सम्पादित पाठ (Combined)</span>
                            <span className="text-[10px] text-amber-600 font-bold">वर्तमान</span>
                          </span>
                          <div className="p-3 bg-white rounded-xl border border-amber-200/90 text-xs font-devanagari text-stone-900 leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto">
                            {currentSlice || (
                              <span className="text-stone-400 italic font-devanagari">
                                {isHi ? '(संयुक्त पाठ अनुपलब्ध)' : '(No combined text)'}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })()}
                </div>
              ) : (
                /* TAB 2: EDIT LOG DIFFS (builder_correction_history) */
                <div className="flex flex-col gap-3">
                  {historyEntries.length === 0 ? (
                    <p className="text-xs text-stone-400 font-devanagari text-center py-8">
                      {isHi ? 'कोई संशोधन इतिहास उपलब्ध नहीं है।' : 'No revision history recorded yet.'}
                    </p>
                  ) : (
                    historyEntries.map((entry) => (
                      <div
                        key={entry.id}
                        className="p-3.5 rounded-2xl border border-stone-200 bg-[#fcfbfa] flex flex-col gap-2"
                      >
                        <div className="flex items-center justify-between text-xs font-devanagari">
                          <span className="font-bold text-stone-800">
                            {entry.reason || (isHi ? 'मैन्युअल संशोधन' : 'Manual Edit')}
                          </span>
                          <span className="text-stone-400 font-mono text-[11px]">
                            {new Date(entry.created_at).toLocaleString()}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-[11px] text-stone-500 font-mono">
                          <span>शब्द परिवर्तन: {entry.words_changed}</span>
                          <span>|</span>
                          <span>वर्ण परिवर्तन: {entry.chars_changed}</span>
                        </div>
                        {entry.diff_summary && (
                          <pre className="p-2.5 rounded-xl bg-stone-900 text-stone-200 font-mono text-[11px] overflow-x-auto whitespace-pre-wrap max-h-48">
                            {entry.diff_summary}
                          </pre>
                        )}
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
