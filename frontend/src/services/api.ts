import type {
  DocumentData,
  PageData,
  CorrectionLog,
  BenchmarkCase,
  CropSuggestionResponse,
  ImageAdjustmentSettings,
  CompressionMode,
  CompressionMetadata,
  CompressionInfoResponse,
  OcrEngine,
  ComparisonData
} from '../types';

export const BACKEND_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
const API_BASE = `${BACKEND_URL}/api`;

export const getStorageUrl = (path: string): string => {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `${BACKEND_URL}${cleanPath}`;
};

/**
 * Robust JSON response handler that prevents "Unexpected end of JSON input"
 * or "Unexpected token '<'" crashes on empty/HTML responses.
 */
async function handleResponse<T = any>(res: Response, defaultError = 'Request failed'): Promise<T> {
  const text = await res.text();
  let json: any = null;
  if (text) {
    try {
      json = JSON.parse(text);
    } catch {
      json = null;
    }
  }

  if (!res.ok) {
    const errorMsg = json?.detail || json?.message || (text && text.length < 200 ? text : null);
    throw new Error(errorMsg || `${defaultError} (HTTP ${res.status})`);
  }

  if (json === null) {
    if (res.status === 204 || !text.trim()) {
      return {} as T;
    }
    throw new Error('Server returned an invalid or non-JSON response');
  }

  return json as T;
}

export const api = {
  async getHealth() {
    const res = await fetch(`${API_BASE}/health`);
    return handleResponse(res, 'Health check failed');
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
    return handleResponse(res, 'Upload failed');
  },

  async processDocument(docId: string, pageNumber?: number) {
    const url = pageNumber 
      ? `${API_BASE}/process/${docId}?page_number=${pageNumber}`
      : `${API_BASE}/process/${docId}`;
    const res = await fetch(url, { method: 'POST' });
    return handleResponse(res, 'Processing failed');
  },

  async listDocuments(search?: string, collection?: string): Promise<{ documents: DocumentData[]; count: number }> {
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    if (collection) params.append('collection', collection);
    const res = await fetch(`${API_BASE}/documents?${params.toString()}`);
    return handleResponse(res, 'Failed to fetch documents');
  },

  async getDocument(docId: string): Promise<{ document: DocumentData; pages: PageData[]; correction_logs: CorrectionLog[] }> {
    const res = await fetch(`${API_BASE}/documents/${docId}`);
    return handleResponse(res, 'Document not found');
  },

  async getPage(docId: string, pageNumber: number): Promise<PageData> {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}`);
    return handleResponse(res, 'Page not found');
  },

  async updateWord(docId: string, pageNumber: number, wordIndex: number, correctedText: string, reason = 'manual_correction') {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/word`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ word_index: wordIndex, corrected_text: correctedText, reason }),
    });
    return handleResponse(res, 'Failed to update word');
  },

  async updatePageText(docId: string, pageNumber: number, verifiedText: string, markConfirmed = false, textVersion = 'reviewed') {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/text`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ verified_text: verifiedText, mark_confirmed: markConfirmed, text_version: textVersion }),
    });
    return handleResponse(res, 'Failed to update page text');
  },

  async retryPage(docId: string, pageNumber: number) {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/retry`, {
      method: 'POST',
    });
    return handleResponse(res, 'Failed to retry page processing');
  },

  async getPageStatus(docId: string, pageNumber: number) {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/status`);
    return handleResponse(res, 'Failed to fetch page status');
  },

  async getDocumentUnresolved(docId: string) {
    const res = await fetch(`${API_BASE}/documents/${docId}/unresolved`);
    return handleResponse(res, 'Failed to fetch unresolved details');
  },

  async suggestCrop(docId: string, pageNumber: number): Promise<CropSuggestionResponse> {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/suggest-crop`, {
      method: 'POST',
    });
    return handleResponse(res, 'Failed to fetch smart crop suggestion');
  },

  async adjustImage(docId: string, pageNumber: number, settings: ImageAdjustmentSettings): Promise<{ success: boolean; page: PageData; adjustment: any }> {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/adjust`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    });
    return handleResponse(res, 'Failed to adjust image');
  },

  async resetAdjustment(docId: string, pageNumber: number, runOcr = true): Promise<{ success: boolean; page: PageData }> {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/reset-adjustment?run_ocr=${runOcr}`, {
      method: 'POST',
    });
    return handleResponse(res, 'Failed to reset image adjustment');
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
    return handleResponse(res, 'Failed to compress image');
  },

  async getCompressionInfo(docId: string, pageNumber: number): Promise<CompressionInfoResponse> {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/compression-info`);
    return handleResponse(res, 'Failed to fetch compression information');
  },

  async comparePageOcr(docId: string, pageNumber: number, groundTruth?: string): Promise<ComparisonData> {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/compare-ocr`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ground_truth: groundTruth || null }),
    });
    return handleResponse(res, 'Failed to compare OCR engines');
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
    return handleResponse(res, 'Failed to fetch comparison details');
  },

  async selectPreferredEngine(docId: string, pageNumber: number, engine: 'tesseract' | 'easyocr', selectedText?: string) {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/select-engine`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engine, selected_text: selectedText || null }),
    });
    return handleResponse(res, 'Failed to select preferred engine');
  },

  async getOcrEngines() {
    const res = await fetch(`${API_BASE}/ocr/engines`);
    return handleResponse(res, 'Failed to fetch OCR engines');
  },

  async deleteDocument(docId: string) {
    const res = await fetch(`${API_BASE}/documents/${docId}`, { method: 'DELETE' });
    return handleResponse(res, 'Failed to delete document');
  },

  getExportUrl(docId: string, format: 'txt' | 'docx' | 'json' | 'html', textVersion: 'reviewed' | 'confirmed' | 'original_ocr' = 'reviewed') {
    return `${API_BASE}/export/${docId}?format=${format}&text_version=${textVersion}`;
  },

  async listSamples(): Promise<{ samples: Array<{ id: string; title: string; filename: string; collection: string; desc: string }> }> {
    const res = await fetch(`${API_BASE}/samples`);
    return handleResponse(res, 'Failed to list samples');
  },

  async loadSample(sampleId: string): Promise<{ success: boolean; document_id: string; title: string }> {
    const res = await fetch(`${API_BASE}/samples/load/${sampleId}`, { method: 'POST' });
    return handleResponse(res, 'Failed to load sample');
  },

  async getBenchmarks(): Promise<{ benchmarks: BenchmarkCase[] }> {
    const res = await fetch(`${API_BASE}/benchmark`);
    return handleResponse(res, 'Failed to fetch benchmarks');
  },

  async evaluateBenchmark(caseId: string, extractedText: string) {
    const formData = new FormData();
    formData.append('case_id', caseId);
    formData.append('extracted_text', extractedText);
    const res = await fetch(`${API_BASE}/benchmark/evaluate`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse(res, 'Failed to evaluate benchmark');
  }
};
