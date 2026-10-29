import React, { useState, useRef, useEffect } from 'react';
import { X, UploadCloud, Camera, FileText, Sparkles, AlertCircle, FileCheck2, ShieldCheck, Zap } from 'lucide-react';
import type { Language } from '../i18n/translations';
import { translations } from '../i18n/translations';
import type { CompressionMode } from '../types';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: (docId: string, shouldAdjust?: boolean) => void;
  onLoadSample: (sampleId: string) => void;
  samples: Array<{ id: string; title: string; filename: string; collection: string; desc: string }>;
  lang: Language;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onUploadSuccess,
  onLoadSample,
  samples,
  lang,
}) => {
  const t = translations[lang];
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState<string>('');
  const [collection, setCollection] = useState<string>('सामान्य (General)');
  const [compressionMode, setCompressionMode] = useState<CompressionMode>('smart');
  const [adjustBeforeOcr, setAdjustBeforeOcr] = useState<boolean>(true);
  const [autoProcess, setAutoProcess] = useState<boolean>(true);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);

  // Escape key closes modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      setFile(selected);
      if (!title) {
        setTitle(selected.name.replace(/\.[^/.]+$/, ''));
      }
      setError(null);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const selected = e.dataTransfer.files[0];
      setFile(selected);
      if (!title) {
        setTitle(selected.name.replace(/\.[^/.]+$/, ''));
      }
      setError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('कृपया कोई चित्र अथवा PDF संचिका चुनें।');
      return;
    }

    try {
      setIsUploading(true);
      setError(null);
      const formData = new FormData();
      formData.append('file', file);
      if (title) formData.append('title', title);
      formData.append('collection_name', collection);
      formData.append('compression_mode', compressionMode);
      const shouldAutoProcess = !adjustBeforeOcr && autoProcess;
      formData.append('auto_process', shouldAutoProcess ? 'true' : 'false');

      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Upload failed');
      }

      const data = await res.json();
      onUploadSuccess(data.document_id, adjustBeforeOcr);
      onClose();
    } catch (err: any) {
      setError(err.message || 'संचिका अपलोड में त्रुटि हुई।');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/60 backdrop-blur-xs p-3 sm:p-4 animate-in fade-in duration-150"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-modal-title"
    >
      <div 
        className="bg-white rounded-2xl sm:rounded-3xl max-w-2xl w-full p-4 sm:p-7 shadow-2xl border border-stone-200 max-h-[92vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-3 sm:pb-4 border-b border-stone-100">
          <div>
            <h2 id="upload-modal-title" className="text-lg sm:text-xl font-bold text-stone-900 font-devanagari">
              {t.uploadTitle}
            </h2>
            <p className="text-xs text-stone-500 mt-0.5 font-devanagari">
              {t.uploadDesc}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 sm:p-2 rounded-xl text-stone-400 hover:text-stone-700 hover:bg-stone-100 transition-colors"
            aria-label={t.close}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mt-3.5 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-900 text-xs flex items-center gap-2 font-devanagari">
            <AlertCircle className="w-4 h-4 text-rose-700 shrink-0" />
            <span className="flex-1">{error}</span>
            <button 
              type="button" 
              onClick={() => setError(null)} 
              className="text-rose-600 hover:text-rose-800"
              aria-label="Dismiss error"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 sm:mt-5 space-y-4">
          {/* Drag & Drop Area */}
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-5 sm:p-7 text-center cursor-pointer transition-all ${
              file
                ? 'border-emerald-500 bg-emerald-50/30'
                : 'border-stone-300 hover:border-vedic-500 hover:bg-stone-50/60'
            }`}
            tabIndex={0}
            role="button"
            aria-label="File upload dropzone"
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                fileInputRef.current?.click();
              }
            }}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept=".jpg,.jpeg,.png,.webp,.pdf"
              className="hidden"
            />
            <input
              type="file"
              ref={cameraInputRef}
              onChange={handleFileChange}
              accept="image/*"
              capture="environment"
              className="hidden"
            />

            {file ? (
              <div className="flex flex-col items-center">
                <div className="w-12 h-12 rounded-2xl bg-emerald-100 text-emerald-800 flex items-center justify-center mb-2 shadow-2xs">
                  <FileCheck2 className="w-6 h-6 text-emerald-700" />
                </div>
                <span className="font-semibold text-sm text-stone-900 break-all">
                  {file.name}
                </span>
                <span className="text-xs text-stone-500 mt-0.5">
                  ({(file.size / (1024 * 1024)).toFixed(2)} MB)
                </span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                  }}
                  className="mt-2 text-xs text-rose-600 hover:underline font-devanagari font-semibold"
                >
                  बदलें (Choose another)
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center">
                <div className="w-12 h-12 rounded-2xl bg-vedic-100 text-vedic-800 flex items-center justify-center mb-2 shadow-2xs">
                  <UploadCloud className="w-6 h-6 text-vedic-700" />
                </div>
                <span className="font-semibold text-sm text-stone-900 font-devanagari">
                  {t.dragDropText}
                </span>
                <span className="text-xs text-stone-500 mt-1 font-devanagari">
                  {t.orClickText}
                </span>

                {/* Mobile Camera Upload Button */}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    cameraInputRef.current?.click();
                  }}
                  className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-stone-100 hover:bg-stone-200 text-stone-800 text-xs font-semibold font-devanagari transition-colors"
                >
                  <Camera className="w-3.5 h-3.5 text-vedic-700" />
                  <span>{t.cameraButton}</span>
                </button>
              </div>
            )}
          </div>

          {/* Form fields: Title & Collection */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
            <div>
              <label htmlFor="upload-title-input" className="block text-xs font-semibold text-stone-700 mb-1 font-devanagari">
                {t.docTitleLabel}
              </label>
              <input
                id="upload-title-input"
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={t.docTitlePlaceholder}
                className="w-full px-3.5 py-2.5 rounded-xl border border-stone-300 focus:outline-none focus:ring-2 focus:ring-vedic-500 text-sm font-devanagari"
              />
            </div>

            <div>
              <label htmlFor="upload-collection-select" className="block text-xs font-semibold text-stone-700 mb-1 font-devanagari">
                {t.collectionLabel}
              </label>
              <select
                id="upload-collection-select"
                value={collection}
                onChange={(e) => setCollection(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-stone-300 focus:outline-none focus:ring-2 focus:ring-vedic-500 text-sm font-devanagari bg-white"
              >
                {Object.values(t.collections).map((cName) => (
                  <option key={cName} value={cName}>
                    {cName}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Compression & Quality Preset Selector */}
          <div className="bg-stone-50 border border-stone-200/80 rounded-xl p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-stone-700 flex items-center gap-1.5 font-devanagari">
                <Zap className="w-3.5 h-3.5 text-amber-600" />
                {t.compressionModeLabel}
              </span>
              <span className="inline-flex items-center gap-1 text-[11px] text-emerald-700 font-medium">
                <ShieldCheck className="w-3.5 h-3.5" />
                {t.archivalIntegrityBadge}
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
              {[
                { id: 'smart' as CompressionMode, label: t.modeSmart, desc: 'Lossless WebP' },
                { id: 'lossless' as CompressionMode, label: t.modeLossless, desc: 'Bit-perfect' },
                { id: 'high_quality' as CompressionMode, label: t.modeHighQuality, desc: 'Q92 Near-lossless' },
                { id: 'original' as CompressionMode, label: t.modeOriginal, desc: 'No compression' },
              ].map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setCompressionMode(m.id)}
                  className={`px-2 py-1.5 rounded-lg text-left border transition-all text-xs ${
                    compressionMode === m.id
                      ? 'bg-vedic-700 text-white border-vedic-700 shadow-2xs'
                      : 'bg-white text-stone-700 border-stone-200 hover:bg-stone-100'
                  }`}
                >
                  <div className="font-semibold font-devanagari text-[11.5px] leading-tight truncate">{m.label}</div>
                  <div className={`text-[10px] truncate ${compressionMode === m.id ? 'text-amber-200' : 'text-stone-400'}`}>
                    {m.desc}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2 pt-1">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="adjustBeforeOcrCheck"
                checked={adjustBeforeOcr}
                onChange={(e) => setAdjustBeforeOcr(e.target.checked)}
                className="w-4 h-4 rounded text-amber-600 focus:ring-amber-500 border-stone-300"
              />
              <label htmlFor="adjustBeforeOcrCheck" className="text-xs font-semibold text-stone-800 font-devanagari cursor-pointer select-none">
                ✨ {t.adjustBeforeOcrCheckbox}
              </label>
            </div>

            {!adjustBeforeOcr && (
              <div className="flex items-center gap-2 pl-6">
                <input
                  type="checkbox"
                  id="autoProcessCheck"
                  checked={autoProcess}
                  onChange={(e) => setAutoProcess(e.target.checked)}
                  className="w-4 h-4 rounded text-vedic-700 focus:ring-vedic-500 border-stone-300"
                />
                <label htmlFor="autoProcessCheck" className="text-xs text-stone-600 font-devanagari cursor-pointer select-none">
                  {t.autoProcessCheckbox}
                </label>
              </div>
            )}
          </div>

          <button
            type="submit"
            disabled={!file || isUploading}
            className="w-full py-2.5 sm:py-3 rounded-xl bg-vedic-700 hover:bg-vedic-800 disabled:opacity-50 text-white font-bold text-sm shadow-2xs transition-colors flex items-center justify-center gap-2 font-devanagari"
          >
            {isUploading ? (
              <span>{t.uploadingStatus}</span>
            ) : (
              <>
                <FileText className="w-4 h-4" />
                <span>{t.submitUpload}</span>
              </>
            )}
          </button>
        </form>

        {/* Preloaded Sample Library Quick Selection */}
        <div className="mt-6 pt-5 border-t border-stone-200">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-4 h-4 text-amber-600" />
            <h3 className="text-xs font-bold text-stone-800 uppercase tracking-wider font-devanagari">
              {t.sampleTitle}
            </h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            {samples.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => {
                  onLoadSample(s.id);
                  onClose();
                }}
                className="p-3 rounded-xl border border-stone-200 bg-stone-50 hover:bg-vedic-50 hover:border-vedic-300 text-left transition-all group"
              >
                <span className="font-bold text-xs text-stone-900 group-hover:text-vedic-950 block font-devanagari truncate">
                  {s.title}
                </span>
                <span className="text-[10px] text-stone-500 font-devanagari block mt-1 line-clamp-2">
                  {s.desc}
                </span>
                <span className="text-[10px] font-semibold text-vedic-700 mt-2 block font-devanagari">
                  {t.loadSampleBtn} →
                </span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
