import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  X, GripVertical, AlertTriangle, Trash2, RefreshCw,
  CheckCircle2, Layers, Image as ImageIcon, Save,
  ArrowUpDown
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
import type { BookData, PageData, MissingPagesReport } from '../types';
import type { Language } from '../i18n/translations';

interface BookPageReorderModalProps {
  book: BookData | null;
  isOpen: boolean;
  onClose: () => void;
  lang?: Language;
  onBookUpdated?: () => void;
}

interface SortablePageItemProps {
  page: PageData;
  index: number;
  isHi: boolean;
  onReplace: (page: PageData) => void;
  onDelete: (page: PageData) => void;
}

const SortablePageItem: React.FC<SortablePageItemProps> = ({
  page,
  index,
  isHi,
  onReplace,
  onDelete
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
    zIndex: isDragging ? 50 : 'auto',
    opacity: isDragging ? 0.6 : 1
  };

  const statusColor = page.status === 'COMPLETED' || page.confirmed_text
    ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
    : 'bg-amber-50 text-amber-800 border-amber-200';

  const statusLabel = page.status === 'COMPLETED' || page.confirmed_text
    ? (isHi ? 'सत्यापित' : 'Verified')
    : (isHi ? 'पुनरावलोकन आवश्यक' : 'Needs Review');

  const imageUrl = getStorageUrl(page.original_image_path);

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`group flex items-center justify-between p-3.5 bg-white rounded-xl border transition-all duration-150 ${
        isDragging
          ? 'border-saffron-500 shadow-xl ring-2 ring-saffron-400/20 bg-amber-50/50'
          : 'border-parchment-200 hover:border-saffron-300 hover:shadow-sm'
      }`}
    >
      <div className="flex items-center space-x-3.5 min-w-0">
        {/* Drag Handle */}
        <button
          type="button"
          {...attributes}
          {...listeners}
          aria-label={isHi ? 'पुनःक्रमबद्ध करने हेतु खींचें' : 'Drag to reorder'}
          className="p-1.5 rounded-lg text-vedic-400 hover:text-vedic-700 hover:bg-parchment-100 cursor-grab active:cursor-grabbing transition-colors focus:outline-none focus:ring-2 focus:ring-saffron-500/20"
        >
          <GripVertical className="w-5 h-5" />
        </button>

        {/* Upload Sequence Order Badge */}
        <div className="flex flex-col items-center justify-center w-8 h-8 rounded-lg bg-parchment-100 text-vedic-700 font-mono text-xs font-bold border border-parchment-200">
          #{index + 1}
        </div>

        {/* Thumbnail Preview */}
        <div className="relative w-12 h-16 rounded-md overflow-hidden bg-parchment-200 border border-parchment-300 flex-shrink-0 flex items-center justify-center">
          {imageUrl ? (
            <img
              src={imageUrl}
              alt={`Page ${page.page_number}`}
              loading="lazy"
              decoding="async"
              className="w-full h-full object-cover"
              onError={(e) => {
                (e.currentTarget as HTMLElement).style.display = 'none';
              }}
            />
          ) : (
            <ImageIcon className="w-5 h-5 text-vedic-400" />
          )}
        </div>

        {/* Page Information */}
        <div className="min-w-0">
          <div className="flex items-center space-x-2">
            <h4 className="font-semibold text-vedic-900 text-sm tracking-tight truncate">
              {isHi ? `पृष्ठ ${page.page_number}` : `Page ${page.page_number}`}
            </h4>
            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium border ${statusColor}`}>
              {statusLabel}
            </span>
          </div>
          <p className="text-xs text-vedic-500 font-mono mt-0.5">
            upload_order: {page.upload_order ?? index + 1}
          </p>
          {page.verified_text && (
            <p className="text-xs text-vedic-600 truncate max-w-md mt-1 font-serif">
              "{page.verified_text.slice(0, 45)}..."
            </p>
          )}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center space-x-1.5 flex-shrink-0">
        <button
          type="button"
          onClick={() => onReplace(page)}
          title={isHi ? 'छवि प्रतिस्थापित करें (पुराना आर्काइव होगा)' : 'Replace image (archives previous)'}
          className="inline-flex items-center space-x-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-vedic-700 hover:text-vedic-900 hover:bg-parchment-100 border border-parchment-300 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5 text-saffron-600" />
          <span className="hidden sm:inline">{isHi ? 'बदलें' : 'Replace'}</span>
        </button>

        <button
          type="button"
          onClick={() => onDelete(page)}
          title={isHi ? 'पृष्ठ हटाएं' : 'Delete page'}
          className="p-1.5 rounded-lg text-red-500 hover:text-red-700 hover:bg-red-50 transition-colors"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};

export const BookPageReorderModal: React.FC<BookPageReorderModalProps> = ({
  book,
  isOpen,
  onClose,
  lang = 'hi',
  onBookUpdated
}) => {
  const isHi = lang === 'hi';

  const [pages, setPages] = useState<PageData[]>([]);
  const [missingReport, setMissingReport] = useState<MissingPagesReport | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Replacement State
  const [replacingPage, setReplacingPage] = useState<PageData | null>(null);
  const [isReplacing, setIsReplacing] = useState<boolean>(false);
  const replaceFileInputRef = useRef<HTMLInputElement>(null);

  // Deletion State
  const [deletingPage, setDeletingPage] = useState<PageData | null>(null);
  const [confirmDeleteOriginal, setConfirmDeleteOriginal] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  // Sensors for DnD
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

  // Fetch Book Pages and Missing Report
  const loadPageData = useCallback(async () => {
    if (!book) return;
    try {
      setIsLoading(true);
      setErrorMsg(null);
      const [pagesRes, missingRes] = await Promise.all([
        api.getBookPages(book.id, 'upload_order'),
        api.getMissingPages(book.id, false)
      ]);

      if (pagesRes && pagesRes.pages) {
        setPages(pagesRes.pages);
      }
      if (missingRes) {
        setMissingReport(missingRes);
      }
    } catch (err: any) {
      console.error('Failed to load book pages:', err);
      setErrorMsg(err.message || (isHi ? 'पृष्ठ सूची लोड करने में त्रुटि।' : 'Failed to load pages.'));
    } finally {
      setIsLoading(false);
    }
  }, [book, isHi]);

  useEffect(() => {
    if (isOpen && book) {
      loadPageData();
      setSaveSuccess(false);
    }
  }, [isOpen, book, loadPageData]);

  // Handle Drag End
  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = pages.findIndex((p) => p.id === active.id);
    const newIndex = pages.findIndex((p) => p.id === over.id);

    if (oldIndex !== -1 && newIndex !== -1) {
      const newPages = arrayMove(pages, oldIndex, newIndex);
      // Immediately reflect new visual order
      setPages(newPages);
      // Save order automatically
      await saveNewOrder(newPages);
    }
  };

  // Persist Reordered List to Backend
  const saveNewOrder = async (orderedList = pages) => {
    if (!book) return;
    try {
      setIsSaving(true);
      setErrorMsg(null);
      const orderedIds = orderedList.map((p) => p.id);
      const res = await api.reorderBookPages(book.id, orderedIds);
      if (res.success) {
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 3000);
        if (onBookUpdated) onBookUpdated();
      }
    } catch (err: any) {
      console.error('Failed to save page order:', err);
      setErrorMsg(err.message || (isHi ? 'क्रम सहेजने में त्रुटि।' : 'Failed to save order.'));
    } finally {
      setIsSaving(false);
    }
  };

  // Trigger Replacement File Input
  const handleStartReplace = (page: PageData) => {
    setReplacingPage(page);
    if (replaceFileInputRef.current) {
      replaceFileInputRef.current.value = '';
      replaceFileInputRef.current.click();
    }
  };

  // Perform Image Replacement
  const handleReplaceFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !replacingPage) return;

    try {
      setIsReplacing(true);
      setErrorMsg(null);
      const res = await api.replacePageImage(replacingPage.id, file, true);
      if (res.success) {
        await loadPageData();
        if (onBookUpdated) onBookUpdated();
      }
    } catch (err: any) {
      console.error('Failed to replace image:', err);
      setErrorMsg(err.message || (isHi ? 'छवि बदलने में त्रुटि।' : 'Failed to replace image.'));
    } finally {
      setIsReplacing(false);
      setReplacingPage(null);
    }
  };

  // Handle Page Deletion
  const handleDeletePageConfirm = async () => {
    if (!deletingPage) return;
    try {
      setIsDeleting(true);
      setErrorMsg(null);
      await api.deletePage(deletingPage.id, confirmDeleteOriginal);
      setDeletingPage(null);
      setConfirmDeleteOriginal(false);
      await loadPageData();
      if (onBookUpdated) onBookUpdated();
    } catch (err: any) {
      console.error('Failed to delete page:', err);
      setErrorMsg(err.message || (isHi ? 'पृष्ठ हटाने में त्रुटि।' : 'Failed to delete page.'));
    } finally {
      setIsDeleting(false);
    }
  };

  if (!isOpen || !book) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-vedic-950/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative w-full max-w-3xl bg-white rounded-2xl shadow-2xl border border-parchment-200 overflow-hidden flex flex-col max-h-[90vh]">
        {/* Hidden replacement file input */}
        <input
          type="file"
          ref={replaceFileInputRef}
          onChange={handleReplaceFileChange}
          accept="image/*"
          className="hidden"
        />

        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-parchment-200 bg-parchment-50 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-saffron-500/10 text-saffron-600 flex items-center justify-center font-bold">
              <ArrowUpDown className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-vedic-900 tracking-tight flex items-center space-x-2">
                <span>{book.name}</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-parchment-200 text-vedic-700 font-mono">
                  {pages.length} / {book.total_pages} {isHi ? 'पृष्ठ' : 'Pages'}
                </span>
              </h3>
              <p className="text-xs text-vedic-600 mt-0.5">
                {isHi
                  ? 'ड्रैग और ड्रॉप द्वारा पृष्ठों के क्रम (upload_order) को व्यवस्थित करें।'
                  : 'Drag and drop to reorder upload sequence.'}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {saveSuccess && (
              <span className="inline-flex items-center space-x-1 text-xs text-emerald-700 font-medium bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-200">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>{isHi ? 'क्रम सहेजा गया' : 'Order saved'}</span>
              </span>
            )}
            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-lg text-vedic-400 hover:text-vedic-700 hover:bg-parchment-100 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Missing Pages Alert */}
        {missingReport && missingReport.has_missing_pages && (
          <div className="px-6 py-3 bg-amber-50 border-b border-amber-200 flex items-center justify-between text-xs text-amber-900">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />
              <span>
                <strong className="font-semibold">
                  {isHi ? 'अनुपलब्ध पृष्ठ (Missing Pages): ' : 'Missing Pages: '}
                </strong>
                {missingReport.missing_gaps.join(', ')}
              </span>
            </div>
            <span className="font-mono text-[11px] text-amber-700">
              {missingReport.missing_gaps.length} {isHi ? 'पृष्ठ छूटे हैं' : 'missing'}
            </span>
          </div>
        )}

        {/* Global Error Banner */}
        {errorMsg && (
          <div className="px-6 py-2.5 bg-red-50 border-b border-red-200 text-xs text-red-700 flex items-center justify-between">
            <span>{errorMsg}</span>
            <button type="button" onClick={() => setErrorMsg(null)} className="text-red-500 hover:text-red-800">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Modal Body / Sortable Page List */}
        <div className="p-6 overflow-y-auto flex-1 bg-parchment-50/50">
          {isLoading ? (
            <div className="py-16 text-center text-vedic-500 text-sm">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-saffron-500" />
              <span>{isHi ? 'पृष्ठ लोड हो रहे हैं...' : 'Loading pages...'}</span>
            </div>
          ) : pages.length === 0 ? (
            <div className="py-16 text-center text-vedic-500 text-sm">
              <Layers className="w-10 h-10 mx-auto mb-2 text-vedic-300" />
              <p className="font-semibold text-vedic-800">
                {isHi ? 'इस ग्रन्थ में अभी कोई पृष्ठ नहीं हैं।' : 'No pages uploaded in this book yet.'}
              </p>
              <p className="text-xs text-vedic-500 mt-1">
                {isHi ? 'स्कैनर या अपलोड मेन्यू से पृष्ठ जोड़ें।' : 'Upload pages from the scanner to manage them.'}
              </p>
            </div>
          ) : (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext items={pages.map((p) => p.id)} strategy={verticalListSortingStrategy}>
                <div className="space-y-2.5">
                  {pages.map((page, index) => (
                    <SortablePageItem
                      key={page.id}
                      page={page}
                      index={index}
                      isHi={isHi}
                      onReplace={handleStartReplace}
                      onDelete={(p) => {
                        setDeletingPage(p);
                        setConfirmDeleteOriginal(false);
                      }}
                    />
                  ))}
                </div>
              </SortableContext>
            </DndContext>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3.5 border-t border-parchment-200 bg-white flex items-center justify-between flex-shrink-0">
          <div className="text-xs text-vedic-500">
            {pages.length > 0 && (
              <span>
                {isHi ? 'परिवर्तन स्वतः सहेजे जाते हैं।' : 'Changes are saved automatically upon drop.'}
              </span>
            )}
          </div>
          <div className="flex items-center space-x-2.5">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-medium text-vedic-700 hover:bg-parchment-100 border border-parchment-300 transition-colors"
            >
              {isHi ? 'पूर्ण' : 'Done'}
            </button>
            <button
              type="button"
              disabled={isSaving || pages.length === 0}
              onClick={() => saveNewOrder()}
              className="inline-flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-semibold text-white bg-saffron-600 hover:bg-saffron-700 shadow-sm transition-colors disabled:opacity-50"
            >
              <Save className="w-3.5 h-3.5" />
              <span>{isSaving ? (isHi ? 'सहेजा जा रहा है...' : 'Saving...') : (isHi ? 'क्रम सहेजें' : 'Save Order')}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Page Delete Confirmation Modal */}
      {deletingPage && (
        <div className="fixed inset-0 z-60 bg-vedic-950/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white rounded-2xl p-6 shadow-2xl border border-red-200">
            <div className="flex items-center space-x-3 text-red-600 mb-3">
              <Trash2 className="w-6 h-6 flex-shrink-0" />
              <h4 className="text-base font-bold text-vedic-900">
                {isHi ? `पृष्ठ ${deletingPage.page_number} हटाएं?` : `Delete Page ${deletingPage.page_number}?`}
              </h4>
            </div>
            <p className="text-xs text-vedic-600 leading-relaxed">
              {isHi
                ? 'यह पृष्ठ प्रणाली से हटा दिया जाएगा। कृपया पुष्टि करें कि क्या आप मूल इमेज फाइल को भी हमेशा के लिए हटाना चाहते हैं:'
                : 'This page record will be removed. Choose whether to permanently delete the original image file:'}
            </p>

            <label className="mt-4 flex items-start space-x-2.5 p-3 rounded-xl bg-parchment-100 border border-parchment-200 cursor-pointer">
              <input
                type="checkbox"
                checked={confirmDeleteOriginal}
                onChange={(e) => setConfirmDeleteOriginal(e.target.checked)}
                className="mt-0.5 rounded border-parchment-400 text-saffron-600 focus:ring-saffron-500"
              />
              <span className="text-xs text-vedic-800 font-medium">
                {isHi
                  ? 'मूल इमेज (R2/Storage) को भी स्थायी रूप से हटाएं'
                  : 'Permanently delete original image from storage/R2'}
              </span>
            </label>

            <div className="mt-6 flex items-center justify-end space-x-2">
              <button
                type="button"
                onClick={() => setDeletingPage(null)}
                className="px-4 py-2 text-xs font-medium text-vedic-700 hover:bg-parchment-100 rounded-xl border border-parchment-300"
              >
                {isHi ? 'रद्द करें' : 'Cancel'}
              </button>
              <button
                type="button"
                disabled={isDeleting}
                onClick={handleDeletePageConfirm}
                className="px-4 py-2 text-xs font-semibold text-white bg-red-600 hover:bg-red-700 rounded-xl transition-colors disabled:opacity-50"
              >
                {isDeleting ? (isHi ? 'हटाया जा रहा है...' : 'Deleting...') : (isHi ? 'हटाएं' : 'Delete')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Replacing Spinner Overlay */}
      {isReplacing && (
        <div className="fixed inset-0 z-60 bg-vedic-950/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl p-6 shadow-2xl text-center max-w-sm">
            <RefreshCw className="w-8 h-8 animate-spin text-saffron-500 mx-auto mb-3" />
            <h4 className="font-bold text-vedic-900 text-sm">
              {isHi ? 'छवि प्रतिस्थापित की जा रही है...' : 'Replacing & Archiving Image...'}
            </h4>
            <p className="text-xs text-vedic-600 mt-1">
              {isHi
                ? 'पुराना मूल originals/archive में सुरक्षित रखा जा रहा है और नया OCR चलाया जा रहा है।'
                : 'Previous original is being archived and new OCR pipeline executed.'}
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
