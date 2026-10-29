import React, { useState, useRef } from 'react';
import { ZoomIn, ZoomOut, RotateCw, Maximize2, Eye, EyeOff, ImageOff, Crop, Undo2, Zap, GitCompare } from 'lucide-react';
import type { WordToken, CompressionMetadata } from '../types';
import type { Language } from '../i18n/translations';
import { translations } from '../i18n/translations';

interface ImageViewerProps {
  originalUrl: string;
  enhancedUrl: string;
  adjustedUrl?: string;
  optimizedUrl?: string;
  compressionMetadata?: CompressionMetadata;
  tokens: WordToken[];
  selectedWordIndex: number | null;
  onSelectWord: (index: number) => void;
  onOpenAdjustment?: () => void;
  onResetAdjustment?: () => Promise<void>;
  onOpenComparison?: () => void;
  lang: Language;
}

export const ImageViewer: React.FC<ImageViewerProps> = ({
  originalUrl,
  enhancedUrl,
  adjustedUrl,
  optimizedUrl,
  compressionMetadata,
  tokens,
  selectedWordIndex,
  onSelectWord,
  onOpenAdjustment,
  onResetAdjustment,
  onOpenComparison,
  lang,
}) => {
  const t = translations[lang];
  const [activeVariant, setActiveVariant] = useState<'original' | 'adjusted' | 'enhanced'>('enhanced');
  const [zoom, setZoom] = useState<number>(1);
  const [rotation, setRotation] = useState<number>(0);
  const [showBboxes, setShowBboxes] = useState<boolean>(true);
  const [naturalDimensions, setNaturalDimensions] = useState<{ width: number; height: number }>({ width: 1, height: 1 });
  const [imgError, setImgError] = useState<boolean>(false);
  const [isResetting, setIsResetting] = useState<boolean>(false);

  const containerRef = useRef<HTMLDivElement>(null);

  const formatImgUrl = (url: string) => {
    if (!url) return '';
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    const cleanPath = url.startsWith('/') ? url : `/${url}`;
    const backendBase = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
    return `${backendBase}${cleanPath}`;
  };

  const currentImgSrc = activeVariant === 'original' 
    ? formatImgUrl(originalUrl)
    : activeVariant === 'adjusted' && adjustedUrl
    ? formatImgUrl(adjustedUrl)
    : formatImgUrl(optimizedUrl || enhancedUrl);

  const handleZoomIn = () => setZoom((prev) => Math.min(Number((prev + 0.25).toFixed(2)), 4.0));
  const handleZoomOut = () => setZoom((prev) => Math.max(Number((prev - 0.25).toFixed(2)), 0.5));
  const handleResetZoom = () => {
    setZoom(1);
    setRotation(0);
  };
  const handleRotate = () => setRotation((prev) => (prev + 90) % 360);

  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    setImgError(false);
    setNaturalDimensions({
      width: img.naturalWidth || 1,
      height: img.naturalHeight || 1,
    });
  };

  const handleResetClick = async () => {
    if (!onResetAdjustment || isResetting) return;
    try {
      setIsResetting(true);
      await onResetAdjustment();
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-stone-100 rounded-2xl border border-stone-200/90 overflow-hidden shadow-2xs">
      {/* Top Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 sm:px-4 py-2.5 sm:py-3 bg-white border-b border-stone-200 text-xs">
        {/* Left Side: Variant Tabs & Adjustment Trigger */}
        <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
          {/* Variant Tabs */}
          <div 
            role="group" 
            aria-label="Image view variant"
            className="flex items-center bg-stone-100 p-0.5 sm:p-1 rounded-xl border border-stone-200/60"
          >
            <button
              type="button"
              onClick={() => setActiveVariant('original')}
              className={`px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-lg text-xs font-devanagari transition-all ${
                activeVariant === 'original'
                  ? 'bg-white text-vedic-950 shadow-2xs font-bold'
                  : 'text-stone-600 hover:text-stone-900 font-medium'
              }`}
              aria-pressed={activeVariant === 'original'}
            >
              {t.originalView}
            </button>
            {adjustedUrl && (
              <button
                type="button"
                onClick={() => setActiveVariant('adjusted')}
                className={`px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-lg text-xs font-devanagari transition-all ${
                  activeVariant === 'adjusted'
                    ? 'bg-white text-vedic-950 shadow-2xs font-bold'
                    : 'text-stone-600 hover:text-stone-900 font-medium'
                }`}
                aria-pressed={activeVariant === 'adjusted'}
              >
                {t.adjustedView}
              </button>
            )}
            <button
              type="button"
              onClick={() => setActiveVariant('enhanced')}
              className={`px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-lg text-xs font-devanagari transition-all ${
                activeVariant === 'enhanced'
                  ? 'bg-white text-vedic-950 shadow-2xs font-bold'
                  : 'text-stone-600 hover:text-stone-900 font-medium'
              }`}
              aria-pressed={activeVariant === 'enhanced'}
            >
              {t.enhancedView}
            </button>
          </div>

          {/* Crop & Rotate Studio Trigger Button */}
          {onOpenAdjustment && (
            <button
              type="button"
              onClick={onOpenAdjustment}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-vedic-300 bg-vedic-50 hover:bg-vedic-100 text-vedic-900 text-xs font-bold transition-colors font-devanagari shadow-2xs"
              title={t.adjustImageBtn}
              aria-label={t.adjustImageBtn}
            >
              <Crop className="w-3.5 h-3.5 text-vedic-700" />
              <span>{t.adjustImageBtn}</span>
            </button>
          )}

          {/* Compare OCR Engines Button */}
          {onOpenComparison && (
            <button
              type="button"
              onClick={onOpenComparison}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-blue-300 bg-blue-50 hover:bg-blue-100 text-blue-900 text-xs font-bold transition-colors font-devanagari shadow-2xs"
              title={t.compareOcrBtn}
              aria-label={t.compareOcrBtn}
            >
              <GitCompare className="w-3.5 h-3.5 text-blue-700" />
              <span>इंजन तुलना</span>
            </button>
          )}

          {/* Reset Adjustment Button (if currently adjusted) */}
          {adjustedUrl && onResetAdjustment && (
            <button
              type="button"
              onClick={handleResetClick}
              disabled={isResetting}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-xl border border-stone-200 bg-white hover:bg-stone-50 text-stone-600 hover:text-stone-900 text-[11px] font-medium transition-colors font-devanagari shadow-2xs"
              title="मूल स्थिति पर लौटें (Reset to original scan)"
            >
              <Undo2 className="w-3 h-3 text-stone-500" />
              <span>रीसेट</span>
            </button>
          )}
          {/* Optimization & Archival Badge */}
          {compressionMetadata && (
            <div 
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-amber-50/80 border border-amber-200/70 text-amber-900 text-[11px] font-mono select-none"
              title={`Original: ${(compressionMetadata.original_size_bytes / 1024).toFixed(0)} KB | Optimized: ${(compressionMetadata.compressed_size_bytes / 1024).toFixed(0)} KB | ${compressionMetadata.effective_mode}`}
            >
              <Zap className="w-3 h-3 text-amber-600 shrink-0" />
              <span>
                {compressionMetadata.savings_percent > 0 
                  ? `-${compressionMetadata.savings_percent.toFixed(0)}%` 
                  : 'Archival'}
              </span>
              <span className="text-[10px] text-amber-700/80 hidden xl:inline font-sans font-medium">
                ({compressionMetadata.is_lossless ? 'Lossless' : (compressionMetadata.is_phone_photo ? `Phone Q${compressionMetadata.quality || 90}` : `Q${compressionMetadata.quality || 92}`)})
              </span>
            </div>
          )}
        </div>

        {/* View Controls Group */}
        <div className="flex items-center gap-1 sm:gap-1.5 flex-wrap">
          {/* Bounding Box Toggle */}
          <button
            type="button"
            onClick={() => setShowBboxes(!showBboxes)}
            className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors font-devanagari ${
              showBboxes
                ? 'bg-amber-50 text-amber-900 border-amber-300'
                : 'bg-white text-stone-600 border-stone-200 hover:bg-stone-50'
            }`}
            title={t.toggleBboxes}
            aria-label={t.toggleBboxes}
            aria-pressed={showBboxes}
          >
            {showBboxes ? <Eye className="w-3.5 h-3.5 text-amber-700" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span className="hidden sm:inline">परिसीमा</span>
          </button>

          <div className="h-4 w-px bg-stone-200 mx-0.5 sm:mx-1" />

          {/* Zoom Out */}
          <button
            type="button"
            onClick={handleZoomOut}
            disabled={zoom <= 0.5}
            className="p-1.5 rounded-lg border border-stone-200 bg-white text-stone-700 hover:bg-stone-50 disabled:opacity-40 transition-colors"
            title={t.zoomOut}
            aria-label={t.zoomOut}
          >
            <ZoomOut className="w-4 h-4" />
          </button>

          <span 
            className="text-stone-600 font-mono text-[11px] min-w-[34px] sm:min-w-[40px] text-center select-none"
            aria-label={`Zoom level ${Math.round(zoom * 100)} percent`}
          >
            {Math.round(zoom * 100)}%
          </span>

          {/* Zoom In */}
          <button
            type="button"
            onClick={handleZoomIn}
            disabled={zoom >= 4.0}
            className="p-1.5 rounded-lg border border-stone-200 bg-white text-stone-700 hover:bg-stone-50 disabled:opacity-40 transition-colors"
            title={t.zoomIn}
            aria-label={t.zoomIn}
          >
            <ZoomIn className="w-4 h-4" />
          </button>

          {/* Rotate */}
          <button
            type="button"
            onClick={handleRotate}
            className="p-1.5 rounded-lg border border-stone-200 bg-white text-stone-700 hover:bg-stone-50 transition-colors"
            title={t.rotateRight}
            aria-label={t.rotateRight}
          >
            <RotateCw className="w-4 h-4" />
          </button>

          {/* Reset View */}
          <button
            type="button"
            onClick={handleResetZoom}
            className="p-1.5 rounded-lg border border-stone-200 bg-white text-stone-700 hover:bg-stone-50 transition-colors"
            title={t.resetZoom}
            aria-label={t.resetZoom}
          >
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Canvas Viewport */}
      <div
        ref={containerRef}
        className="relative flex-1 overflow-auto p-3 sm:p-5 flex items-center justify-center bg-stone-900/5 select-none min-h-[360px]"
        tabIndex={0}
        aria-label="Document Image Canvas"
      >
        {imgError || !currentImgSrc ? (
          <div className="flex flex-col items-center justify-center p-8 text-stone-400 text-center font-devanagari">
            <ImageOff className="w-10 h-10 mb-2 opacity-60" />
            <p className="text-sm">दस्तावेज़ छवि उपलब्ध नहीं है अथवा लोड नहीं हो सकी।</p>
          </div>
        ) : (
          <div
            className="relative transition-transform duration-100 ease-out inline-block shadow-md rounded-lg overflow-hidden bg-white max-w-full"
            style={{
              transform: `scale(${zoom}) rotate(${rotation}deg)`,
              transformOrigin: 'center center',
            }}
          >
            <img
              src={currentImgSrc}
              alt="Source Hindi Document"
              onLoad={handleImageLoad}
              onError={() => setImgError(true)}
              className="max-w-none block pointer-events-none object-contain"
              style={{ maxHeight: '70vh', maxWidth: '100%' }}
            />

            {/* Word Bounding Boxes Layer */}
            {showBboxes && tokens.map((tok) => {
              const [x, y, w, h] = tok.bbox;
              const leftPct = (x / naturalDimensions.width) * 100;
              const topPct = (y / naturalDimensions.height) * 100;
              const widthPct = (w / naturalDimensions.width) * 100;
              const heightPct = (h / naturalDimensions.height) * 100;

              const isSelected = selectedWordIndex === tok.index;
              const isDisagreement = Boolean(tok.disagreement_type);
              const isAnomaly = Boolean(tok.unicode_anomalies && tok.unicode_anomalies.length > 0);
              const isLowConf = tok.confidence < 65.0;

              let borderStyle = 'border-emerald-500/70 bg-emerald-500/10 hover:bg-emerald-500/30';
              if (isDisagreement) {
                borderStyle = 'border-amber-500 bg-amber-500/25 hover:bg-amber-500/40';
              } else if (isAnomaly) {
                borderStyle = 'border-purple-600 bg-purple-500/25 hover:bg-purple-500/40';
              } else if (isLowConf) {
                borderStyle = 'border-rose-500 bg-rose-500/25 hover:bg-rose-500/40';
              }

              if (isSelected) {
                borderStyle = 'ring-2 ring-vedic-600 border-vedic-700 bg-vedic-500/35 z-20 shadow-xs';
              }

              return (
                <div
                  key={`bbox-${tok.index}`}
                  role="button"
                  tabIndex={0}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectWord(tok.index);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelectWord(tok.index);
                    }
                  }}
                  className={`absolute border rounded-[2px] cursor-pointer transition-all ${borderStyle}`}
                  style={{
                    left: `${leftPct}%`,
                    top: `${topPct}%`,
                    width: `${widthPct}%`,
                    height: `${heightPct}%`,
                  }}
                  title={`${tok.text} (विश्वास: ${tok.confidence}%)`}
                  aria-label={`${tok.text}, विश्वास ${tok.confidence} प्रतिशत`}
                />
              );
            })}
          </div>
        )}
      </div>

      {/* Legend Footer */}
      <div className="flex flex-wrap items-center justify-between gap-2 sm:gap-3 px-3 sm:px-4 py-2 bg-stone-50 border-t border-stone-200 text-[11px] text-stone-600 font-devanagari">
        <div className="flex items-center gap-2.5 sm:gap-4 flex-wrap">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block shrink-0" />
            <span>सत्यापित (Verified)</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block shrink-0" />
            <span>मतभेद (Disagreement)</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-purple-600 inline-block shrink-0" />
            <span>यूनिकोड (Linguistic)</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block shrink-0" />
            <span>संदिग्ध (Low Conf)</span>
          </span>
        </div>
        <div className="font-mono text-[10px] text-stone-500">
          {tokens.length} शब्द चिह्नित
        </div>
      </div>
    </div>
  );
};
