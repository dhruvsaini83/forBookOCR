import type { DocumentData, PageData, CorrectionLog, BenchmarkCase } from '../types';

const API_BASE = 'http://127.0.0.1:8000/api';

export const api = {
  async getHealth() {
    const res = await fetch(`${API_BASE}/health`);
    return res.json();
  },

  async uploadDocument(file: File, title?: string, collection?: string, autoProcess = true): Promise<{ success: boolean; document_id: string; title: string; total_pages: number }> {
    const formData = new FormData();
    formData.append('file', file);
    if (title) formData.append('title', title);
    if (collection) formData.append('collection_name', collection);
    formData.append('auto_process', autoProcess ? 'true' : 'false');

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

  async updatePageText(docId: string, pageNumber: number, verifiedText: string, markConfirmed = false) {
    const res = await fetch(`${API_BASE}/documents/${docId}/pages/${pageNumber}/text`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ verified_text: verifiedText, mark_confirmed: markConfirmed }),
    });
    return res.json();
  },

  async deleteDocument(docId: string) {
    const res = await fetch(`${API_BASE}/documents/${docId}`, { method: 'DELETE' });
    return res.json();
  },

  getExportUrl(docId: string, format: 'txt' | 'docx' | 'json' | 'html') {
    return `${API_BASE}/export/${docId}?format=${format}`;
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
