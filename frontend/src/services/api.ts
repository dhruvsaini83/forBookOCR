import type { DocumentData, PageData, CorrectionLog, BenchmarkCase, CropSuggestionResponse, ImageAdjustmentSettings, CompressionMode, CompressionMetadata, CompressionInfoResponse, OcrEngine, ComparisonData } from '../types';

const API_BASE = '/api';

export const api = {
  async getHealth() {
    const res = await fetch(`${API_BASE}/health`);
    return res.json();
  },

  async uploadDocument(
    file: File,
    title?: string,
    collection?: string,
    autoProcess = true,
    compressionMode: CompressionMode = 'smart',
    ocrEngine: OcrEngine = 'tesseract'
  ): Promise<{ success: boolean; document_id: string; title: string; total_pages: number; ocr_engine?: string }> {
    const formData = new FormData();
    formData.append('file', file);
    if (title) formData.append('title', title);
    if (collection) formData.append('collection_name', collection);
    formData.append('auto_process', autoProcess ? 'true' : 'false');
    formData.append('compression_mode', compressionMode);
    formData.append('ocr_engine', ocrEngine);

    const res = await fetch(`${API_BASE}/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Upload failed');
    }
    return res.json();
  },

  async processDocument(docId: string, pageNumber?: number) {
    const url = pageNumber 
      ? `${API_BASE}/process/${docId}?page_number=${pageNumber}`
      : `${API_BASE}/process/${docId}`;
    const res = await fetch(url, { method: 'POST' });
    if (!res.ok) throw new Error('Processing failed');
    return res.json();
  },

  async listDocuments(search?: string, collection?: string): Promise<{ documents: DocumentData[]; count: number }> {
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    if (collection) params.append('collection', collection);
    const res = await fetch(`${API_BASE}/documents?${params.toString()}`);
    return res.json();
  },

  async getDocument(docId: string): Promise<{ document: DocumentData; pages: PageData[]; correction_logs: CorrectionLog[] }> {
    const res = await fetch(`${API_BASE}/documents/${docId}`);
    if (!res.ok) throw new Error('Document not found');
    return res.json();
  },

  async getPage(docId: string, pageNumber: number): Promise<PageData> {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}`);
    if (!res.ok) throw new Error('Page not found');
    return res.json();
  },

  async updateWord(docId: string, pageNumber: number, wordIndex: number, correctedText: string, reason = 'manual_correction') {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/word`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ word_index: wordIndex, corrected_text: correctedText, reason }),
    });
    return res.json();
  },

  async updatePageText(docId: string, pageNumber: number, verifiedText: string, markConfirmed = false, textVersion = 'reviewed') {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/text`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ verified_text: verifiedText, mark_confirmed: markConfirmed, text_version: textVersion }),
    });
    return res.json();
  },

  async retryPage(docId: string, pageNumber: number) {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/retry`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to retry page processing');
    return res.json();
  },

  async getPageStatus(docId: string, pageNumber: number) {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/status`);
    if (!res.ok) throw new Error('Failed to fetch page status');
    return res.json();
  },

  async getDocumentUnresolved(docId: string) {
    const res = await fetch(`${API_BASE}/documents/${docId}/unresolved`);
    if (!res.ok) throw new Error('Failed to fetch unresolved details');
    return res.json();
  },

  async suggestCrop(docId: string, pageNumber: number): Promise<CropSuggestionResponse> {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/suggest-crop`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to fetch smart crop suggestion');
    return res.json();
  },

  async adjustImage(docId: string, pageNumber: number, settings: ImageAdjustmentSettings): Promise<{ success: boolean; page: PageData; adjustment: any }> {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/adjust`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to adjust image');
    }
    return res.json();
  },

  async resetAdjustment(docId: string, pageNumber: number, runOcr = true): Promise<{ success: boolean; page: PageData }> {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/reset-adjustment?run_ocr=${runOcr}`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to reset image adjustment');
    return res.json();
  },

  async compressPage(
    docId: string,
    pageNumber: number,
    settings: {
      mode: CompressionMode;
      max_dimension?: number;
      quality?: number;
      apply_to_all_pages?: boolean;
      run_ocr?: boolean;
    }
  ): Promise<{ success: boolean; page: PageData; compression: CompressionMetadata }> {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/compress`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to compress image');
    }
    return res.json();
  },

  async getCompressionInfo(docId: string, pageNumber: number): Promise<CompressionInfoResponse> {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/compression-info`);
    if (!res.ok) throw new Error('Failed to fetch compression information');
    return res.json();
  },

  async comparePageOcr(docId: string, pageNumber: number, groundTruth?: string): Promise<ComparisonData> {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/compare-ocr`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ground_truth: groundTruth || null }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to compare OCR engines');
    }
    return res.json();
  },

  async getPageComparison(docId: string, pageNumber: number): Promise<{
    document_id: string;
    page_number: number;
    has_comparison: boolean;
    ocr_engine: string;
    tesseract_text: string;
    easyocr_text: string;
    comparison: ComparisonData;
  }> {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/comparison`);
    if (!res.ok) throw new Error('Failed to fetch comparison details');
    return res.json();
  },

  async selectPreferredEngine(docId: string, pageNumber: number, engine: 'tesseract' | 'easyocr', selectedText?: string) {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/select-engine`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engine, selected_text: selectedText || null }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to select preferred engine');
    }
    return res.json();
  },

  async getOcrEngines() {
    const res = await fetch(`${API_BASE}/ocr/engines`);
    return res.json();
  },

  async deleteDocument(docId: string) {
    const res = await fetch(`${API_BASE}/documents/${docId}`, { method: 'DELETE' });
    return res.json();
  },

  getExportUrl(docId: string, format: 'txt' | 'docx' | 'json' | 'html', textVersion: 'reviewed' | 'confirmed' | 'original_ocr' = 'reviewed') {
    return `${API_BASE}/export/${docId}?format=${format}&text_version=${textVersion}`;
  },

  async listSamples(): Promise<{ samples: Array<{ id: string; title: string; filename: string; collection: string; desc: string }> }> {
    const res = await fetch(`${API_BASE}/samples`);
    return res.json();
  },

  async loadSample(sampleId: string): Promise<{ success: boolean; document_id: string; title: string }> {
    const res = await fetch(`${API_BASE}/samples/load/${sampleId}`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to load sample');
    return res.json();
  },

  async getBenchmarks(): Promise<{ benchmarks: BenchmarkCase[] }> {
    const res = await fetch(`${API_BASE}/benchmark`);
    return res.json();
  },

  async evaluateBenchmark(caseId: string, extractedText: string) {
    const formData = new FormData();
    formData.append('case_id', caseId);
    formData.append('extracted_text', extractedText);
    const res = await fetch(`${API_BASE}/benchmark/evaluate`, {
      method: 'POST',
      body: formData,
    });
    return res.json();
  }
};
