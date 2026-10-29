import React, { useState, useRef } from 'react';
import { ZoomIn, ZoomOut, RotateCw, Maximize2, Eye, EyeOff } from 'lucide-react';
import type { WordToken } from '../types';
import type { Language } from '../i18n/translations';
import { translations } from '../i18n/translations';

interface ImageViewerProps {
  originalUrl: string;
  enhancedUrl: string;
  tokens: WordToken[];
  selectedWordIndex: number | null;
  onSelectWord: (index: number) => void;
  lang: Language;
}

export const ImageViewer: React.FC<ImageViewerProps> = ({
  originalUrl,
  enhancedUrl,
  tokens,
  selectedWordIndex,
  onSelectWord,
  lang,
}) => {
  const t = translations[lang];
  const [activeVariant, setActiveVariant] = useState<'original' | 'enhanced'>('enhanced');
  const [zoom, setZoom] = useState<number>(1);
  const [rotation, setRotation] = useState<number>(0);
  const [showBboxes, setShowBboxes] = useState<boolean>(true);
  const [naturalDimensions, setNaturalDimensions] = useState<{ width: number; height: number }>({ width: 1, height: 1 });

  const containerRef = useRef<HTMLDivElement>(null);

  const currentImgSrc = activeVariant === 'original' 
    ? (originalUrl.startsWith('http') ? originalUrl : `http://127.0.0.1:8000${originalUrl}`)
    : (enhancedUrl.startsWith('http') ? enhancedUrl : `http://127.0.0.1:8000${enhancedUrl}`);

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 0.25, 4.0));
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 0.25, 0.5));
  const handleResetZoom = () => {
    setZoom(1);
    setRotation(0);
  };
  const handleRotate = () => setRotation((prev) => (prev + 90) % 360);

  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    setNaturalDimensions({
      width: img.naturalWidth || 1,
      height: img.naturalHeight || 1,
    });
  };

  return (
    <div className="flex flex-col h-full bg-stone-100 rounded-2xl border border-stone-200 overflow-hidden shadow-sm">
      {/* Top Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 bg-white border-b border-stone-200 text-xs">
        {/* Variant Tabs */}
        <div className="flex items-center bg-stone-100 p-1 rounded-xl">
          <button
            onClick={() => setActiveVariant('original')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeVariant === 'original'
                ? 'bg-white text-vedic-900 shadow-xs font-semibold'
                : 'text-stone-600 hover:text-stone-900'
            }`}
          >
            {t.originalView}
          </button>
          <button
            onClick={() => setActiveVariant('enhanced')}
            className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
              activeVariant === 'enhanced'
                ? 'bg-white text-vedic-900 shadow-xs font-semibold'
                : 'text-stone-600 hover:text-stone-900'
            }`}
          >
            {t.enhancedView}
          </button>
        </div>

        {/* View Controls */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setShowBboxes(!showBboxes)}
            className={`inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
              showBboxes
                ? 'bg-amber-50 text-amber-800 border-amber-300'
                : 'bg-white text-stone-600 border-stone-200 hover:bg-stone-50'
            }`}
            title={t.toggleBboxes}
          >
            {showBboxes ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span className="hidden sm:inline">परिसीमा</span>
          </button>

          <div className="h-4 w-px bg-stone-200 mx-1" />

          <button
            onClick={handleZoomIn}
            className="p-1.5 rounded-lg border border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
            title={t.zoomIn}
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <span className="text-stone-500 font-mono text-[11px] min-w-[36px] text-center">
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={handleZoomOut}
            className="p-1.5 rounded-lg border border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
            title={t.zoomOut}
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={handleRotate}
            className="p-1.5 rounded-lg border border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
            title={t.rotateRight}
          >
            <RotateCw className="w-4 h-4" />
          </button>
          <button
            onClick={handleResetZoom}
            className="p-1.5 rounded-lg border border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
            title={t.resetZoom}
          >
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Canvas Viewport */}
      <div
        ref={containerRef}
        className="relative flex-1 overflow-auto p-4 flex items-center justify-center bg-stone-900/5 select-none"
        style={{ minHeight: '440px' }}
      >
        <div
          className="relative transition-transform duration-100 ease-out inline-block shadow-lg rounded-lg overflow-hidden bg-white"
          style={{
            transform: `scale(${zoom}) rotate(${rotation}deg)`,
            transformOrigin: 'center center',
          }}
        >
          <img
            src={currentImgSrc}
            alt="Source Hindi Document"
            onLoad={handleImageLoad}
            className="max-w-none block pointer-events-none"
            style={{ maxHeight: '72vh' }}
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

            let borderStyle = 'border-emerald-500/60 bg-emerald-500/10 hover:bg-emerald-500/25';
            if (isDisagreement) {
              borderStyle = 'border-amber-500 bg-amber-500/20 hover:bg-amber-500/35';
            } else if (isAnomaly) {
              borderStyle = 'border-purple-600 bg-purple-500/20 hover:bg-purple-500/35';
            } else if (isLowConf) {
              borderStyle = 'border-rose-500 bg-rose-500/20 hover:bg-rose-500/35';
            }

            if (isSelected) {
              borderStyle = 'ring-3 ring-vedic-600 border-vedic-600 bg-vedic-500/30 z-20';
            }

            return (
              <div
                key={`bbox-${tok.index}`}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectWord(tok.index);
                }}
                className={`absolute border rounded-[2px] cursor-pointer transition-all ${borderStyle}`}
                style={{
                  left: `${leftPct}%`,
                  top: `${topPct}%`,
                  width: `${widthPct}%`,
                  height: `${heightPct}%`,
                }}
                title={`${tok.text} (विश्वास: ${tok.confidence}%)`}
              />
            );
          })}
        </div>
      </div>

      {/* Legend Footer */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2 bg-stone-50 border-t border-stone-200 text-[11px] text-stone-600">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />
            सत्यापित (Verified)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" />
            मतभेद (Disagreement)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-purple-600 inline-block" />
            यूनिकोड/प्राचीन (Linguistic)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block" />
            संदिग्ध (Low Conf)
          </span>
        </div>
        <div className="font-mono text-[10px] text-stone-400">
          {tokens.length} देवनागरी शब्द चिह्नित
        </div>
      </div>
    </div>
  );
};
