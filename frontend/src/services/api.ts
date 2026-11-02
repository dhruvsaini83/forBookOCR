import type {
  BookData,
  CreateBookPayload,
  UpdateBookPayload,
  DashboardMetrics,
  MissingPagesReport,
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
  ComparisonData,
  BookBuilderData,
  BookBuilderResponse,
  BuilderHistoryEntry,
  BuilderStageComparisonItem,
  BuilderDraftItem,
  BhajanSearchFilter,
  BookBhajansResponse,
  BhajanSearchResponse,
  ExportFormat,
  ExportScope,
  BookExportOptions,
  BookExportResponse
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

  async suggestCrop(docId: string, pageNumber: number, rotation: number = 0, fineRotation: number = 0): Promise<CropSuggestionResponse> {
    const params = new URLSearchParams();
    if (rotation) params.append('rotation', rotation.toString());
    if (fineRotation) params.append('fine_rotation', fineRotation.toString());
    const query = params.toString() ? `?${params.toString()}` : '';
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/suggest-crop${query}`, {
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

  async selectPreferredEngine(docId: string, pageNumber: number, engine: 'tesseract' | 'easyocr' | 'paddleocr', selectedText?: string) {
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
  },

  async listBooks(status?: string, search?: string): Promise<{ success: boolean; books: BookData[]; total_books: number; dashboard_metrics: DashboardMetrics }> {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    if (search) params.append('search', search);
    const res = await fetch(`${API_BASE}/books?${params.toString()}`);
    return handleResponse(res, 'Failed to fetch books');
  },

  async getBook(bookId: string): Promise<{ success: boolean; book: BookData; dashboard_metrics: DashboardMetrics }> {
    const res = await fetch(`${API_BASE}/books/${bookId}`);
    return handleResponse(res, 'Failed to fetch book');
  },

  async createBook(payload: CreateBookPayload): Promise<{ success: boolean; book: BookData; dashboard_metrics: DashboardMetrics }> {
    const res = await fetch(`${API_BASE}/books`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return handleResponse(res, 'Failed to create book');
  },

  async updateBook(bookId: string, payload: UpdateBookPayload): Promise<{ success: boolean; book: BookData; dashboard_metrics: DashboardMetrics }> {
    const res = await fetch(`${API_BASE}/books/${bookId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    return handleResponse(res, 'Failed to update book');
  },

  async deleteBook(bookId: string, confirm = true): Promise<{ success: boolean; message: string; deleted_pages_count: number; dashboard_metrics: DashboardMetrics }> {
    const res = await fetch(`${API_BASE}/books/${bookId}?confirm=${confirm}`, {
      method: 'DELETE'
    });
    return handleResponse(res, 'Failed to delete book');
  },

  async getDashboardMetrics(): Promise<{ success: boolean; dashboard_metrics: DashboardMetrics }> {
    const res = await fetch(`${API_BASE}/dashboard/metrics`);
    return handleResponse(res, 'Failed to fetch dashboard metrics');
  },
  async getMissingPages(bookId: string, upToTotal = false): Promise<MissingPagesReport> {
    const res = await fetch(`${API_BASE}/books/${bookId}/missing-pages?up_to_total=${upToTotal}`);
    return handleResponse(res, 'Failed to fetch missing pages report');
  },

  async reorderBookPages(bookId: string, orderedPageIds: string[]): Promise<{ success: boolean; book_id: string; reordered_count: number; pages: PageData[] }> {
    const res = await fetch(`${API_BASE}/books/${bookId}/pages/reorder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ordered_page_ids: orderedPageIds }),
    });
    return handleResponse(res, 'Failed to reorder book pages');
  },

  async getBookPages(bookId: string, sortBy = 'upload_order'): Promise<{ success: boolean; pages: PageData[]; total_pages: number }> {
    const res = await fetch(`${API_BASE}/books/${bookId}/pages?sort_by=${sortBy}`);
    return handleResponse(res, 'Failed to fetch book pages');
  },

  async deletePage(pageId: string, confirmDeleteOriginal = false): Promise<{ success: boolean; message: string; original_image_deleted: boolean }> {
    const res = await fetch(`${API_BASE}/pages/${pageId}?confirm_delete_original=${confirmDeleteOriginal}`, {
      method: 'DELETE',
    });
    return handleResponse(res, 'Failed to delete page');
  },

  async replacePageImage(pageId: string, file: File, autoProcess = true, ocrEngine = 'tesseract'): Promise<{ success: boolean; page_id: string; archived_path: string; new_image_url: string; status: string; page: PageData }> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('auto_process', String(autoProcess));
    formData.append('ocr_engine', ocrEngine);
    const res = await fetch(`${API_BASE}/pages/${pageId}/replace`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse(res, 'Failed to replace page image');
  },
  async checkBookDuplicates(bookId: string, threshold = 8): Promise<{
    success: boolean;
    book_id: string;
    book_name: string;
    total_scanned_pages: number;
    duplicate_pairs_count: number;
    has_duplicates: boolean;
    threshold: number;
    duplicate_pairs: Array<{
      page1: { id: string; page_number: number; upload_order: number; preview_url: string; phash: string };
      page2: { id: string; page_number: number; upload_order: number; preview_url: string; phash: string };
      hamming_distance: number;
      similarity_percentage: number;
    }>;
  }> {
    const res = await fetch(`${API_BASE}/books/${bookId}/check-duplicates?threshold=${threshold}`, {
      method: 'POST'
    });
    return handleResponse(res, 'Failed to check duplicates');
  },
  async getBookBuilder(bookId: string): Promise<BookBuilderResponse> {
    const res = await fetch(`${API_BASE}/books/${bookId}/builder`);
    return handleResponse(res, 'Failed to fetch book builder collection');
  },

  async builderAddPages(bookId: string, pageIds: string[]): Promise<BookBuilderResponse> {
    const res = await fetch(`${API_BASE}/books/${bookId}/builder/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ page_ids: pageIds }),
    });
    return handleResponse(res, 'Failed to add pages to book builder');
  },

  async builderRemovePage(bookId: string, pageId: string): Promise<BookBuilderResponse> {
    const res = await fetch(`${API_BASE}/books/${bookId}/builder/remove`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ page_id: pageId }),
    });
    return handleResponse(res, 'Failed to remove page from book builder');
  },

  async builderReorderPages(bookId: string, orderedPageNumbers: number[]): Promise<BookBuilderResponse> {
    const res = await fetch(`${API_BASE}/books/${bookId}/builder/reorder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ordered_page_numbers: orderedPageNumbers }),
    });
    return handleResponse(res, 'Failed to reorder book builder pages');
  },

  async builderEditText(bookId: string, combinedText: string): Promise<{ success: boolean; book_id: string; message: string; builder: BookBuilderData }> {
    const res = await fetch(`${API_BASE}/books/${bookId}/builder/edit`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ combined_text: combinedText }),
    });
    return handleResponse(res, 'Failed to edit builder combined text');
  },
  async builderCombinedEdit(bookId: string, combinedText: string, reason?: string): Promise<{
    success: boolean;
    book_id: string;
    message: string;
    builder: BookBuilderData;
    history_entry: BuilderHistoryEntry;
  }> {
    const res = await fetch(`${API_BASE}/books/${bookId}/builder/combined-edit`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ combined_text: combinedText, reason: reason || 'CombinedEditor update' }),
    });
    return handleResponse(res, 'Failed to update combined text and history');
  },

  async getBuilderHistory(bookId: string, limit = 50): Promise<{
    success: boolean;
    book_id: string;
    history: BuilderHistoryEntry[];
  }> {
    const res = await fetch(`${API_BASE}/books/${bookId}/builder/history?limit=${limit}`);
    return handleResponse(res, 'Failed to fetch builder edit history');
  },

  async getBuilderStageComparison(bookId: string): Promise<{
    success: boolean;
    book_id: string;
    comparison: BuilderStageComparisonItem[];
  }> {
    const res = await fetch(`${API_BASE}/books/${bookId}/builder/stage-comparison`);
    return handleResponse(res, 'Failed to fetch stage comparison');
  },

  async saveBuilderDraft(bookId: string, name: string, text: string): Promise<{
    success: boolean;
    book_id: string;
    draft: BuilderDraftItem;
  }> {
    const res = await fetch(`${API_BASE}/books/${bookId}/builder/drafts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, text }),
    });
    return handleResponse(res, 'Failed to save builder draft');
  },

  async listBuilderDrafts(bookId: string): Promise<{
    success: boolean;
    book_id: string;
    drafts: BuilderDraftItem[];
  }> {
    const res = await fetch(`${API_BASE}/books/${bookId}/builder/drafts`);
    return handleResponse(res, 'Failed to list builder drafts');
  },

  async deleteBuilderDraft(bookId: string, draftId: string): Promise<{
    success: boolean;
    book_id: string;
    deleted: boolean;
    message: string;
  }> {
    const res = await fetch(`${API_BASE}/books/${bookId}/builder/drafts/${draftId}`, {
      method: 'DELETE',
    });
    return handleResponse(res, 'Failed to delete builder draft');
  },

  async loadBuilderDraft(bookId: string, draftId: string): Promise<{
    success: boolean;
    book_id: string;
    draft: BuilderDraftItem;
    message: string;
  }> {
    const res = await fetch(`${API_BASE}/books/${bookId}/builder/drafts/${draftId}/load`, {
      method: 'POST',
    });
    return handleResponse(res, 'Failed to load builder draft');
  },

  async getBookBhajans(bookId: string): Promise<BookBhajansResponse> {
    const res = await fetch(`${API_BASE}/books/${bookId}/bhajans`);
    return handleResponse(res, 'Failed to fetch book bhajans');
  },

  async searchBookBhajans(bookId: string, query: string, filter: BhajanSearchFilter = 'all'): Promise<BhajanSearchResponse> {
    const params = new URLSearchParams({ q: query, filter });
    const res = await fetch(`${API_BASE}/books/${bookId}/search?${params.toString()}`);
    return handleResponse(res, 'Failed to search bhajans');
  },

  async exportBook(
    bookId: string,
    format: ExportFormat = 'pdf',
    scope: ExportScope = 'complete',
    pages?: string,
    options?: BookExportOptions
  ): Promise<BookExportResponse> {
    const params = new URLSearchParams({
      format,
      scope,
      include_page_numbers: options?.include_page_numbers !== false ? 'true' : 'false',
      include_page_breaks: options?.include_page_breaks !== false ? 'true' : 'false',
      only_verified: options?.only_verified ? 'true' : 'false',
    });
    if (pages) {
      params.append('pages', pages);
    }
    const res = await fetch(`${API_BASE}/books/${bookId}/export?${params.toString()}`);
    return handleResponse(res, 'Failed to export book');
  },

  getBookExportDirectUrl(
    bookId: string,
    format: ExportFormat = 'pdf',
    scope: ExportScope = 'complete',
    pages?: string,
    options?: BookExportOptions
  ): string {
    const params = new URLSearchParams({
      format,
      scope,
      include_page_numbers: options?.include_page_numbers !== false ? 'true' : 'false',
      include_page_breaks: options?.include_page_breaks !== false ? 'true' : 'false',
      only_verified: options?.only_verified ? 'true' : 'false',
      download: 'true'
    });
    if (pages) {
      params.append('pages', pages);
    }
    return `${API_BASE}/books/${bookId}/export?${params.toString()}`;
  },
};
