import React, { useState, useRef, useEffect, useCallback } from 'react';
import { 
  X, Crop, RotateCcw, RotateCw, RefreshCw, 
  Undo2, Redo2, Check, ZoomIn, ZoomOut, 
  ChevronLeft, ChevronRight, Sliders, AlertCircle, Sparkles,
  Zap, CheckCircle2, Eye
} from 'lucide-react';
import type { Language } from '../i18n/translations';
import { translations } from '../i18n/translations';
import type { CropBox, ImageAdjustmentSettings, CompressionMode, CompressionInfoResponse } from '../types';
import { api } from '../services/api';

interface ImageAdjustmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  documentId: string;
  pageNumber: number;
  totalPages: number;
  originalImageUrl: string;
  currentAdjustment?: ImageAdjustmentSettings;
  onApplySuccess: (pageNumber: number) => Promise<void>;
  onSkip?: () => void;
  lang: Language;
}

interface HistoryState {
  crop: CropBox | null;
  rotation: number;
  fineRotation: number;
}

export const ImageAdjustmentModal: React.FC<ImageAdjustmentModalProps> = ({
  isOpen,
  onClose,
  documentId,
  pageNumber,
  totalPages,
  originalImageUrl,
  currentAdjustment,
  onApplySuccess,
  onSkip,
  lang,
}) => {
  const t = translations[lang];

  // Active page within the adjustment studio
  const [activePage, setActivePage] = useState<number>(pageNumber);
  
  // Natural image dimensions
  const [imgNaturalSize, setImgNaturalSize] = useState<{ width: number; height: number }>({ width: 1, height: 1 });
  const [isImgLoaded, setIsImgLoaded] = useState<boolean>(false);

  // Adjustment states
  const [rotation, setRotation] = useState<number>(currentAdjustment?.rotation || 0);
  const [fineRotation, setFineRotation] = useState<number>(currentAdjustment?.fine_rotation || 0);
  const [crop, setCrop] = useState<CropBox | null>(currentAdjustment?.crop || null);
  const [isCropEnabled, setIsCropEnabled] = useState<boolean>(Boolean(currentAdjustment?.crop));
  const [applyToAllPages, setApplyToAllPages] = useState<boolean>(false);

  // Zoom inside preview studio
  const [zoom, setZoom] = useState<number>(1);

  // Undo / Redo Stacks
  const [undoStack, setUndoStack] = useState<HistoryState[]>([]);
  const [redoStack, setRedoStack] = useState<HistoryState[]>([]);

  // UI status
  const [isApplying, setIsApplying] = useState<boolean>(false);
  const [isAutoDetecting, setIsAutoDetecting] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Compression & Quality State
  const [compressionMode, setCompressionMode] = useState<CompressionMode>('smart');
  const [compressionInfo, setCompressionInfo] = useState<CompressionInfoResponse | null>(null);
  const [isCompressing, setIsCompressing] = useState<boolean>(false);

  // Dragging & Resizing State
  // handle: 'move' | 'nw' | 'ne' | 'se' | 'sw' | 'n' | 's' | 'e' | 'w' | null
  const [activeHandle, setActiveHandle] = useState<string | null>(null);
  const dragStartRef = useRef<{ clientX: number; clientY: number; crop: CropBox }>({ clientX: 0, clientY: 0, crop: { x: 0, y: 0, width: 0, height: 0 } });

  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  // Helper to push history state before changes
  const pushHistory = useCallback(() => {
    setUndoStack((prev) => [
      ...prev.slice(-15),
      { crop, rotation, fineRotation }
    ]);
    setRedoStack([]);
  }, [crop, rotation, fineRotation]);

  // Synchronize on modal open or page change
  useEffect(() => {
    setActivePage(pageNumber);
    setRotation(currentAdjustment?.rotation || 0);
    setFineRotation(currentAdjustment?.fine_rotation || 0);
    setCrop(currentAdjustment?.crop || null);
    setIsCropEnabled(Boolean(currentAdjustment?.crop));
    setUndoStack([]);
    setRedoStack([]);
    setStatusMessage(null);
    setErrorMessage(null);
    setIsImgLoaded(false);
  }, [isOpen, pageNumber, currentAdjustment]);

  const fetchCompressionInfo = useCallback(async () => {
    try {
      const info = await api.getCompressionInfo(documentId, activePage);
      setCompressionInfo(info);
      if (info?.mode) {
        setCompressionMode(info.mode);
      }
    } catch {
      // ignore
    }
  }, [documentId, activePage]);

  useEffect(() => {
    if (isOpen) {
      fetchCompressionInfo();
    }
  }, [isOpen, activePage, fetchCompressionInfo]);

  const handleCompressionModeChange = async (newMode: CompressionMode) => {
    setCompressionMode(newMode);
    try {
      setIsCompressing(true);
      const res = await api.compressPage(documentId, activePage, {
        mode: newMode,
        run_ocr: false
      });
      if (res?.compression) {
        setCompressionInfo((prev) => prev ? {
          ...prev,
          mode: newMode,
          effective_mode: res.compression.effective_mode,
          optimized_size_bytes: res.compression.compressed_size_bytes,
          bytes_saved: res.compression.bytes_saved,
          savings_percent: res.compression.savings_percent,
          is_lossless: res.compression.is_lossless,
          is_fallback: res.compression.is_fallback,
        } : null);
        setStatusMessage(t.compressionAppliedToast);
        setTimeout(() => setStatusMessage(null), 3000);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Compression failed');
    } finally {
      setIsCompressing(false);
    }
  };

  // Escape key handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !isApplying) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isApplying, onClose]);

  if (!isOpen) return null;

  const formatImgUrl = (url: string) => {
    if (!url) return '';
    return url.startsWith('http') || url.startsWith('/') ? url : `/${url}`;
  };

  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    const nw = img.naturalWidth || 1;
    const nh = img.naturalHeight || 1;
    setImgNaturalSize({ width: nw, height: nh });
    setIsImgLoaded(true);

    // If no crop currently set, initialize default crop covering full image
    if (!crop) {
      setCrop({ x: 0, y: 0, width: nw, height: nh });
    }
  };

  // Dimensions under current rotation
  const isRotated90or270 = (rotation % 180) !== 0;
  const currentViewWidth = isRotated90or270 ? imgNaturalSize.height : imgNaturalSize.width;
  const currentViewHeight = isRotated90or270 ? imgNaturalSize.width : imgNaturalSize.height;

  // --- Rotations ---
  const handleRotateCw = () => {
    pushHistory();
    setRotation((prev) => (prev + 90) % 360);
    // Reset crop to full new bounds on 90 deg rotation to avoid out-of-bound distortion
    setCrop({ x: 0, y: 0, width: currentViewHeight, height: currentViewWidth });
  };

  const handleRotateCcw = () => {
    pushHistory();
    setRotation((prev) => (prev + 270) % 360);
    setCrop({ x: 0, y: 0, width: currentViewHeight, height: currentViewWidth });
  };

  const handleRotate180 = () => {
    pushHistory();
    setRotation((prev) => (prev + 180) % 360);
  };

  const handleFineRotateChange = (newAngle: number) => {
    setFineRotation(newAngle);
  };

  // --- Smart Auto Crop ---
  const handleSmartAutoCrop = async () => {
    try {
      setIsAutoDetecting(true);
      setErrorMessage(null);
      const res = await api.suggestCrop(documentId, activePage);
      if (res.crop) {
        pushHistory();
        setCrop(res.crop);
        setIsCropEnabled(true);
        setStatusMessage(
          res.is_fallback
            ? 'पूर्ण पृष्ठ अनुशंसित (सीमाएं अस्पष्ट)'
            : `स्मार्ट सीमा संज्ञान सक्रिय (${Math.round((res.confidence || 0.9) * 100)}% सटीकता)`
        );
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'स्मार्ट क्रॉप सुझाव में त्रुटि हुई।');
    } finally {
      setIsAutoDetecting(false);
    }
  };

  // --- Toggle / Reset Crop ---
  const handleToggleCrop = () => {
    pushHistory();
    if (isCropEnabled) {
      setIsCropEnabled(false);
      setCrop({ x: 0, y: 0, width: currentViewWidth, height: currentViewHeight });
    } else {
      setIsCropEnabled(true);
      if (!crop) {
        setCrop({ x: 0, y: 0, width: currentViewWidth, height: currentViewHeight });
      }
    }
  };

  const handleResetAll = () => {
    pushHistory();
    setRotation(0);
    setFineRotation(0);
    setIsCropEnabled(false);
    setCrop({ x: 0, y: 0, width: imgNaturalSize.width, height: imgNaturalSize.height });
    setStatusMessage('सभी समायोजन रीसेट किए गए।');
  };

  // --- Undo / Redo ---
  const handleUndo = () => {
    if (undoStack.length === 0) return;
    const previous = undoStack[undoStack.length - 1];
    setRedoStack((prev) => [...prev, { crop, rotation, fineRotation }]);
    setUndoStack((prev) => prev.slice(0, -1));
    setCrop(previous.crop);
    setRotation(previous.rotation);
    setFineRotation(previous.fineRotation);
    setIsCropEnabled(Boolean(previous.crop));
  };

  const handleRedo = () => {
    if (redoStack.length === 0) return;
    const next = redoStack[redoStack.length - 1];
    setUndoStack((prev) => [...prev, { crop, rotation, fineRotation }]);
    setRedoStack((prev) => prev.slice(0, -1));
    setCrop(next.crop);
    setRotation(next.rotation);
    setFineRotation(next.fineRotation);
    setIsCropEnabled(Boolean(next.crop));
  };

  // --- Pointer Drag / Resize for Crop Box ---
  const handlePointerDown = (handle: string, e: React.PointerEvent) => {
    if (!crop || !imgRef.current) return;
    e.preventDefault();
    e.stopPropagation();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);

    pushHistory();
    setActiveHandle(handle);
    dragStartRef.current = {
      clientX: e.clientX,
      clientY: e.clientY,
      crop: { ...crop },
    };
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!activeHandle || !crop || !imgRef.current) return;
    e.preventDefault();

    const img = imgRef.current;
    const rect = img.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;

    // Scale factors from screen pixels to image coordinate units
    const scaleX = currentViewWidth / rect.width;
    const scaleY = currentViewHeight / rect.height;

    const deltaX = (e.clientX - dragStartRef.current.clientX) * scaleX;
    const deltaY = (e.clientY - dragStartRef.current.clientY) * scaleY;

    const initial = dragStartRef.current.crop;
    const minW = Math.max(40, currentViewWidth * 0.05);
    const minH = Math.max(40, currentViewHeight * 0.05);

    let nextX = initial.x;
    let nextY = initial.y;
    let nextW = initial.width;
    let nextH = initial.height;

    if (activeHandle === 'move') {
      nextX = Math.max(0, Math.min(currentViewWidth - initial.width, initial.x + deltaX));
      nextY = Math.max(0, Math.min(currentViewHeight - initial.height, initial.y + deltaY));
    } else {
      // Corner & Edge adjustments
      if (activeHandle.includes('e')) {
        nextW = Math.max(minW, Math.min(currentViewWidth - initial.x, initial.width + deltaX));
      }
      if (activeHandle.includes('s')) {
        nextH = Math.max(minH, Math.min(currentViewHeight - initial.y, initial.height + deltaY));
      }
      if (activeHandle.includes('w')) {
        const potentialW = initial.width - deltaX;
        if (potentialW >= minW && initial.x + deltaX >= 0) {
          nextX = initial.x + deltaX;
          nextW = potentialW;
        }
      }
      if (activeHandle.includes('n')) {
        const potentialH = initial.height - deltaY;
        if (potentialH >= minH && initial.y + deltaY >= 0) {
          nextY = initial.y + deltaY;
          nextH = potentialH;
        }
      }
    }

    setCrop({
      x: Math.round(nextX),
      y: Math.round(nextY),
      width: Math.round(nextW),
      height: Math.round(nextH),
    });
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    if (activeHandle) {
      try {
        (e.target as HTMLElement).releasePointerCapture(e.pointerId);
      } catch (err) {
        // ignore
      }
      setActiveHandle(null);
    }
  };

  // --- Apply & Start OCR ---
  const handleApply = async () => {
    try {
      setIsApplying(true);
      setErrorMessage(null);

      const finalCrop = isCropEnabled && crop ? crop : null;
      const settings: ImageAdjustmentSettings = {
        crop: finalCrop,
        rotation,
        fine_rotation: Number(fineRotation.toFixed(1)),
        apply_to_all_pages: applyToAllPages,
        run_ocr: true,
      };

      await api.adjustImage(documentId, activePage, settings);
      if (compressionMode) {
        try {
          await api.compressPage(documentId, activePage, {
            mode: compressionMode,
            apply_to_all_pages: applyToAllPages,
            run_ocr: false
          });
        } catch {
          // ignore
        }
      }
      await onApplySuccess(activePage);
      onClose();
    } catch (err: any) {
      setErrorMessage(err.message || t.adjustFailedToast);
    } finally {
      setIsApplying(false);
    }
  };

  // Calculate crop rectangle as percentage of displayed image
  const cropLeftPct = crop ? (crop.x / currentViewWidth) * 100 : 0;
  const cropTopPct = crop ? (crop.y / currentViewHeight) * 100 : 0;
  const cropWidthPct = crop ? (crop.width / currentViewWidth) * 100 : 100;
  const cropHeightPct = crop ? (crop.height / currentViewHeight) * 100 : 100;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-stone-950/80 backdrop-blur-xs p-2 sm:p-4 animate-in fade-in duration-150"
      role="dialog"
      aria-modal="true"
      aria-labelledby="adjustment-studio-title"
    >
      <div 
        className="bg-white rounded-2xl sm:rounded-3xl max-w-5xl w-full h-[94vh] flex flex-col shadow-2xl border border-stone-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 sm:px-6 py-3 border-b border-stone-200 bg-white shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-vedic-100 text-vedic-800 flex items-center justify-center shadow-2xs">
              <Crop className="w-4 h-4 text-vedic-700" />
            </div>
            <div>
              <h2 id="adjustment-studio-title" className="text-sm sm:text-base font-bold text-stone-900 font-devanagari">
                {t.adjustmentStudioTitle}
              </h2>
              <span className="text-[11px] text-stone-500 font-devanagari block">
                {totalPages > 1 ? `पृष्ठ ${activePage} / ${totalPages}` : t.adjustmentStudioDesc}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Multi-page switcher inside studio */}
            {totalPages > 1 && (
              <div className="flex items-center gap-1 bg-stone-100 p-1 rounded-xl text-xs font-devanagari border border-stone-200 mr-2">
                <button
                  type="button"
                  onClick={() => setActivePage((p) => Math.max(1, p - 1))}
                  disabled={activePage <= 1 || isApplying}
                  className="p-1 rounded-lg bg-white border border-stone-200 text-stone-700 disabled:opacity-40"
                  aria-label={t.prevPage}
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                </button>
                <span className="px-1.5 font-semibold text-stone-800 text-xs">
                  {activePage} / {totalPages}
                </span>
                <button
                  type="button"
                  onClick={() => setActivePage((p) => Math.min(totalPages, p + 1))}
                  disabled={activePage >= totalPages || isApplying}
                  className="p-1 rounded-lg bg-white border border-stone-200 text-stone-700 disabled:opacity-40"
                  aria-label={t.nextPage}
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            <button
              type="button"
              onClick={onClose}
              disabled={isApplying}
              className="p-1.5 rounded-xl text-stone-400 hover:text-stone-700 hover:bg-stone-100 transition-colors"
              aria-label={t.close}
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Primary Interactive Toolbar */}
        <div className="px-3 sm:px-6 py-2.5 bg-stone-50 border-b border-stone-200/90 flex flex-wrap items-center justify-between gap-2 shrink-0 text-xs font-devanagari">
          {/* Main Action Group: Auto Crop, Crop Toggle, Rotations */}
          <div className="flex items-center gap-1 sm:gap-1.5 flex-wrap">
            {/* Smart Auto Crop */}
            <button
              type="button"
              onClick={handleSmartAutoCrop}
              disabled={isAutoDetecting || isApplying}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-white font-semibold shadow-2xs transition-colors"
              title={t.autoCropBtn}
            >
              {isAutoDetecting ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Sparkles className="w-3.5 h-3.5" />
              )}
              <span>{t.autoCropBtn}</span>
            </button>

            {/* Manual Crop Toggle */}
            <button
              type="button"
              onClick={handleToggleCrop}
              className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl border text-xs font-medium transition-colors ${
                isCropEnabled
                  ? 'bg-vedic-50 text-vedic-900 border-vedic-300 font-bold'
                  : 'bg-white text-stone-700 border-stone-200 hover:bg-stone-50'
              }`}
            >
              <Crop className="w-3.5 h-3.5" />
              <span>{isCropEnabled ? t.resetCropBtn : t.manualCropBtn}</span>
            </button>

            <div className="h-4 w-px bg-stone-300 mx-1" />

            {/* Rotate Left 90 */}
            <button
              type="button"
              onClick={handleRotateCcw}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-white border border-stone-200 text-stone-700 hover:bg-stone-100 transition-colors"
              title={t.rotateLeft}
              aria-label={t.rotateLeft}
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">{t.rotateLeft}</span>
            </button>

            {/* Rotate Right 90 */}
            <button
              type="button"
              onClick={handleRotateCw}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-white border border-stone-200 text-stone-700 hover:bg-stone-100 transition-colors"
              title={t.rotateRight}
              aria-label={t.rotateRight}
            >
              <RotateCw className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">{t.rotateRight}</span>
            </button>

            {/* Rotate 180 */}
            <button
              type="button"
              onClick={handleRotate180}
              className="inline-flex items-center gap-1 px-2 py-1.5 rounded-xl bg-white border border-stone-200 text-stone-700 hover:bg-stone-100 transition-colors"
              title={t.rotate180}
              aria-label={t.rotate180}
            >
              <span>180°</span>
            </button>

            {/* Fine Rotation Stepper / Slider */}
            <div className="flex items-center gap-1.5 bg-white px-2.5 py-1 rounded-xl border border-stone-200 text-stone-700">
              <Sliders className="w-3.5 h-3.5 text-stone-400" />
              <span className="text-[11px] text-stone-500">{t.fineRotate}:</span>
              <input
                type="range"
                min="-15"
                max="15"
                step="0.5"
                value={fineRotation}
                onChange={(e) => handleFineRotateChange(parseFloat(e.target.value))}
                className="w-16 sm:w-20 accent-vedic-600 h-1.5 cursor-pointer"
                aria-label={t.fineRotate}
              />
              <span className="font-mono text-[11px] min-w-[32px] text-center font-bold text-stone-800">
                {fineRotation > 0 ? `+${fineRotation}` : fineRotation}°
              </span>
              {fineRotation !== 0 && (
                <button
                  type="button"
                  onClick={() => setFineRotation(0)}
                  className="text-[10px] text-stone-400 hover:text-stone-700 font-mono"
                  title="0° Reset"
                >
                  0°
                </button>
              )}
            </div>
          </div>

          {/* Secondary Group: Undo, Redo, Zoom, Reset */}
          <div className="flex items-center gap-1 sm:gap-1.5">
            <button
              type="button"
              onClick={handleUndo}
              disabled={undoStack.length === 0}
              className="p-1.5 rounded-xl bg-white border border-stone-200 text-stone-700 hover:bg-stone-100 disabled:opacity-30 transition-colors"
              title={t.undoBtn}
              aria-label={t.undoBtn}
            >
              <Undo2 className="w-3.5 h-3.5" />
            </button>

            <button
              type="button"
              onClick={handleRedo}
              disabled={redoStack.length === 0}
              className="p-1.5 rounded-xl bg-white border border-stone-200 text-stone-700 hover:bg-stone-100 disabled:opacity-30 transition-colors"
              title={t.redoBtn}
              aria-label={t.redoBtn}
            >
              <Redo2 className="w-3.5 h-3.5" />
            </button>

            <button
              type="button"
              onClick={() => setZoom((z) => Math.max(0.6, z - 0.2))}
              disabled={zoom <= 0.6}
              className="p-1.5 rounded-xl bg-white border border-stone-200 text-stone-700 hover:bg-stone-100 disabled:opacity-30 transition-colors"
              title={t.zoomOut}
              aria-label={t.zoomOut}
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>

            <span className="font-mono text-[11px] text-stone-500 min-w-[32px] text-center">
              {Math.round(zoom * 100)}%
            </span>

            <button
              type="button"
              onClick={() => setZoom((z) => Math.min(2.5, z + 0.2))}
              disabled={zoom >= 2.5}
              className="p-1.5 rounded-xl bg-white border border-stone-200 text-stone-700 hover:bg-stone-100 disabled:opacity-30 transition-colors"
              title={t.zoomIn}
              aria-label={t.zoomIn}
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>

            <button
              type="button"
              onClick={handleResetAll}
              className="px-2 py-1.5 rounded-xl text-rose-700 hover:bg-rose-50 border border-transparent hover:border-rose-200 text-[11px] font-semibold transition-colors"
              title={t.resetAllBtn}
            >
              {t.resetAllBtn}
            </button>
          </div>
        </div>

        {/* Status / Notice Pill */}
        {statusMessage && (
          <div className="bg-emerald-50 px-4 py-1.5 text-xs text-emerald-800 border-b border-emerald-100 flex items-center justify-between font-devanagari">
            <span className="flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
              {statusMessage}
            </span>
            <button type="button" onClick={() => setStatusMessage(null)} className="text-emerald-700">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {errorMessage && (
          <div className="bg-rose-50 px-4 py-1.5 text-xs text-rose-800 border-b border-rose-100 flex items-center justify-between font-devanagari">
            <span className="flex items-center gap-1.5">
              <AlertCircle className="w-3.5 h-3.5 text-rose-600" />
              {errorMessage}
            </span>
            <button type="button" onClick={() => setErrorMessage(null)} className="text-rose-700">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Smart Compression & Archival Preservation Strip */}
        <div className="bg-stone-100/90 border-b border-stone-200 px-3 sm:px-6 py-2 flex flex-wrap items-center justify-between gap-2 text-xs font-devanagari">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="font-semibold text-stone-700 flex items-center gap-1 text-[11px] mr-1">
              <Zap className="w-3.5 h-3.5 text-amber-600" />
              {t.compressionTabTitle}:
            </span>
            {[
              { id: 'smart' as CompressionMode, label: t.modeSmart },
              { id: 'lossless' as CompressionMode, label: t.modeLossless },
              { id: 'high_quality' as CompressionMode, label: t.modeHighQuality },
              { id: 'original' as CompressionMode, label: t.modeOriginal },
            ].map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => handleCompressionModeChange(m.id)}
                disabled={isCompressing || isApplying}
                className={`px-2.5 py-1 rounded-lg border text-[11px] font-semibold transition-all inline-flex items-center gap-1 ${
                  compressionMode === m.id
                    ? 'bg-vedic-700 text-white border-vedic-700 shadow-2xs'
                    : 'bg-white text-stone-700 border-stone-200 hover:bg-stone-50'
                }`}
              >
                <span>{m.label}</span>
                {compressionMode === m.id && isCompressing && (
                  <RefreshCw className="w-2.5 h-2.5 animate-spin" />
                )}
              </button>
            ))}
          </div>

          {/* Size & Savings metrics pills */}
          {compressionInfo && (
            <div className="flex items-center gap-2 text-[11px] font-mono shrink-0">
              <div className="flex items-center gap-1.5 bg-white border border-stone-200 px-2 py-0.5 rounded-md text-stone-600">
                <span>{(compressionInfo.original_size_bytes / 1024).toFixed(0)} KB</span>
                <span className="text-stone-400">→</span>
                <span className="font-bold text-stone-900">{(compressionInfo.optimized_size_bytes / 1024).toFixed(0)} KB</span>
                {compressionInfo.savings_percent > 0 && (
                  <span className="bg-emerald-100 text-emerald-800 font-bold px-1 py-0.2 rounded text-[10px]">
                    -{compressionInfo.savings_percent.toFixed(1)}%
                  </span>
                )}
              </div>

              {compressionInfo.is_lossless && (
                <span className="inline-flex items-center gap-1 bg-amber-50 text-amber-800 border border-amber-200/80 px-2 py-0.5 rounded-md text-[10px] font-semibold">
                  <CheckCircle2 className="w-3 h-3 text-amber-600" />
                  {t.losslessGuaranteeBadge}
                </span>
              )}

              {/* 100% Zoom toggle for pixel-level inspection */}
              <button
                type="button"
                onClick={() => setZoom(zoom === 1 ? 1.8 : 1)}
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-[10px] font-semibold transition-colors ${
                  zoom > 1 ? 'bg-amber-100 text-amber-900 border-amber-300' : 'bg-white text-stone-600 border-stone-200 hover:bg-stone-50'
                }`}
                title={t.compare100Zoom}
              >
                <Eye className="w-3 h-3 text-stone-600" />
                <span>{zoom > 1 ? '1:1 Reset' : '100% Zoom'}</span>
              </button>
            </div>
          )}
        </div>

        {/* Central Preview & Crop Canvas */}
        <div 
          ref={containerRef}
          className="flex-1 bg-stone-900 overflow-auto relative p-4 flex items-center justify-center select-none"
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
        >
          <div 
            className="relative transition-transform duration-100"
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: 'center center',
            }}
          >
            {/* The Image with rotation applied */}
            <img
              ref={imgRef}
              src={formatImgUrl(originalImageUrl)}
              alt="Scan for adjustment"
              onLoad={handleImageLoad}
              draggable={false}
              className="max-h-[64vh] max-w-full object-contain shadow-2xl rounded-sm transition-transform duration-150"
              style={{
                transform: `rotate(${rotation + fineRotation}deg)`,
              }}
            />

            {/* Crop Overlay when crop is enabled and image is loaded */}
            {isCropEnabled && crop && isImgLoaded && (
              <div 
                className="absolute inset-0 pointer-events-none"
                style={{
                  transform: `rotate(${rotation + fineRotation}deg)`,
                  transformOrigin: 'center center',
                }}
              >
                {/* 4 Outer Darkened Backdrop Panels */}
                <div 
                  className="absolute bg-stone-950/65"
                  style={{ top: 0, left: 0, right: 0, height: `${cropTopPct}%` }}
                />
                <div 
                  className="absolute bg-stone-950/65"
                  style={{ bottom: 0, left: 0, right: 0, height: `${100 - (cropTopPct + cropHeightPct)}%` }}
                />
                <div 
                  className="absolute bg-stone-950/65"
                  style={{ top: `${cropTopPct}%`, left: 0, width: `${cropLeftPct}%`, height: `${cropHeightPct}%` }}
                />
                <div 
                  className="absolute bg-stone-950/65"
                  style={{ top: `${cropTopPct}%`, right: 0, width: `${100 - (cropLeftPct + cropWidthPct)}%`, height: `${cropHeightPct}%` }}
                />

                {/* The Active Crop Box */}
                <div 
                  className="absolute border-2 border-amber-400 bg-transparent pointer-events-auto cursor-move shadow-xs"
                  style={{
                    top: `${cropTopPct}%`,
                    left: `${cropLeftPct}%`,
                    width: `${cropWidthPct}%`,
                    height: `${cropHeightPct}%`,
                  }}
                  onPointerDown={(e) => handlePointerDown('move', e)}
                >
                  {/* Rule-of-thirds grid guides */}
                  <div className="absolute inset-0 grid grid-cols-3 grid-rows-3 pointer-events-none border border-white/20">
                    <div className="border-r border-b border-white/20" />
                    <div className="border-r border-b border-white/20" />
                    <div className="border-b border-white/20" />
                    <div className="border-r border-b border-white/20" />
                    <div className="border-r border-b border-white/20" />
                    <div className="border-b border-white/20" />
                    <div className="border-r border-white/20" />
                    <div className="border-r border-white/20" />
                    <div />
                  </div>

                  {/* Corner Handles */}
                  <div 
                    onPointerDown={(e) => handlePointerDown('nw', e)}
                    className="absolute -top-2.5 -left-2.5 w-6 h-6 flex items-center justify-center cursor-nwse-resize pointer-events-auto"
                  >
                    <div className="w-3.5 h-3.5 bg-white border-2 border-amber-500 rounded-sm shadow-md" />
                  </div>
                  <div 
                    onPointerDown={(e) => handlePointerDown('ne', e)}
                    className="absolute -top-2.5 -right-2.5 w-6 h-6 flex items-center justify-center cursor-nesw-resize pointer-events-auto"
                  >
                    <div className="w-3.5 h-3.5 bg-white border-2 border-amber-500 rounded-sm shadow-md" />
                  </div>
                  <div 
                    onPointerDown={(e) => handlePointerDown('sw', e)}
                    className="absolute -bottom-2.5 -left-2.5 w-6 h-6 flex items-center justify-center cursor-nesw-resize pointer-events-auto"
                  >
                    <div className="w-3.5 h-3.5 bg-white border-2 border-amber-500 rounded-sm shadow-md" />
                  </div>
                  <div 
                    onPointerDown={(e) => handlePointerDown('se', e)}
                    className="absolute -bottom-2.5 -right-2.5 w-6 h-6 flex items-center justify-center cursor-nwse-resize pointer-events-auto"
                  >
                    <div className="w-3.5 h-3.5 bg-white border-2 border-amber-500 rounded-sm shadow-md" />
                  </div>

                  {/* Edge Handles */}
                  <div 
                    onPointerDown={(e) => handlePointerDown('n', e)}
                    className="absolute -top-2 left-1/2 -translate-x-1/2 w-8 h-4 flex items-center justify-center cursor-ns-resize pointer-events-auto"
                  >
                    <div className="w-6 h-2 bg-white border border-amber-500 rounded-full shadow-md" />
                  </div>
                  <div 
                    onPointerDown={(e) => handlePointerDown('s', e)}
                    className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-8 h-4 flex items-center justify-center cursor-ns-resize pointer-events-auto"
                  >
                    <div className="w-6 h-2 bg-white border border-amber-500 rounded-full shadow-md" />
                  </div>
                  <div 
                    onPointerDown={(e) => handlePointerDown('w', e)}
                    className="absolute top-1/2 -left-2 -translate-y-1/2 w-4 h-8 flex items-center justify-center cursor-ew-resize pointer-events-auto"
                  >
                    <div className="w-2 h-6 bg-white border border-amber-500 rounded-full shadow-md" />
                  </div>
                  <div 
                    onPointerDown={(e) => handlePointerDown('e', e)}
                    className="absolute top-1/2 -right-2 -translate-y-1/2 w-4 h-8 flex items-center justify-center cursor-ew-resize pointer-events-auto"
                  >
                    <div className="w-2 h-6 bg-white border border-amber-500 rounded-full shadow-md" />
                  </div>

                  {/* Dimension pill */}
                  <div className="absolute bottom-2 right-2 bg-stone-900/90 text-white font-mono text-[10px] px-2 py-0.5 rounded-md shadow-sm pointer-events-none select-none">
                    {crop.width} × {crop.height} px
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer / Confirmation Bar */}
        <div className="px-4 sm:px-6 py-3 border-t border-stone-200 bg-white flex flex-col sm:flex-row items-center justify-between gap-3 shrink-0">
          <div className="flex items-center gap-3 w-full sm:w-auto">
            {/* Multi-page apply to all checkbox */}
            {totalPages > 1 && (
              <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-stone-700 font-devanagari">
                <input
                  type="checkbox"
                  checked={applyToAllPages}
                  onChange={(e) => setApplyToAllPages(e.target.checked)}
                  className="w-4 h-4 rounded text-vedic-700 focus:ring-vedic-500 border-stone-300"
                />
                <span>{t.applyToAllPages}</span>
              </label>
            )}

            <span className="text-[11px] text-stone-500 font-devanagari hidden md:inline">
              🛡️ {t.matraProtectionNotice}
            </span>
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            {onSkip && (
              <button
                type="button"
                onClick={onSkip}
                disabled={isApplying}
                className="px-3.5 py-2 rounded-xl text-stone-600 hover:text-stone-900 hover:bg-stone-100 font-semibold text-xs transition-colors font-devanagari"
              >
                {t.skipAdjustment}
              </button>
            )}

            <button
              type="button"
              onClick={onClose}
              disabled={isApplying}
              className="px-4 py-2 rounded-xl border border-stone-200 text-stone-700 hover:bg-stone-100 font-semibold text-xs transition-colors font-devanagari"
            >
              {t.cancelAdjustment}
            </button>

            <button
              type="button"
              onClick={handleApply}
              disabled={isApplying}
              className="px-5 py-2 rounded-xl bg-vedic-700 hover:bg-vedic-800 disabled:opacity-50 text-white font-bold text-xs shadow-md transition-colors flex items-center gap-2 font-devanagari"
            >
              {isApplying ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>प्रक्रियाधीन...</span>
                </>
              ) : (
                <>
                  <Check className="w-4 h-4" />
                  <span>{t.applyAndRunOcr}</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
