export type ConfidenceTier = 'high' | 'medium' | 'low';
export type WordStatus = 'verified' | 'needs_review' | 'verified_historical' | 'manually_confirmed';
export type DisagreementType = 'AGREEMENT' | 'MATRA_DISAGREEMENT' | 'GLYPH_CONFUSION' | 'CONJUNCT_DISAGREEMENT' | 'WORD_DISAGREEMENT' | null;

export interface WordToken {
  index: number;
  text: string;
  original_text: string;
  edited_text?: string | null;
  confirmed_text?: string | null;
  correction_status?: 'ORIGINAL' | 'EDITED' | 'CONFIRMED' | string;
  confidence: number;
  confidence_tier: ConfidenceTier;
  bbox: [number, number, number, number]; // [x, y, w, h]
  block_num: number;
  par_num: number;
  line_num: number;
  word_num: number;
  flags: string[];
  status: WordStatus;
  cross_verified?: boolean;
  secondary_text?: string;
  disagreement_type?: DisagreementType;
  discrepancy_note_hi?: string;
  discrepancy_note_en?: string;
  unicode_anomalies?: Array<[string, string, string]>;
  is_historical_spelling?: boolean;
  suggested_correction?: string;
  linguistic_note_hi?: string;
  linguistic_note_en?: string;
  image_crop?: string;
}

export interface QualityMetrics {
  laplacian_variance: number;
  blur_rating: string;
  mean_brightness: number;
  contrast_std: number;
  contrast_rating: string;
  detected_skew_angle: number;
  dimensions: {
    width: number;
    height: number;
  };
  is_quality_acceptable: boolean;
}

export interface StageMetrics {
  stage1: QualityMetrics;
  stage2: {
    engine: string;
    languages: string;
    psm_mode: number;
    word_count: number;
    average_confidence: number;
    processing_time_ms: number;
    high_conf_words: number;
    med_conf_words: number;
    low_conf_words: number;
  };
  stage3: {
    secondary_engine: string;
    total_tokens_evaluated: number;
    agreements: number;
    disagreements: number;
    agreement_rate_pct: number;
    discrepancy_breakdown: Record<string, number>;
  };
  stage4: {
    total_tokens_checked: number;
    unicode_anomalies_detected: number;
    historical_forms_preserved: number;
    advisory_suggestions_generated: number;
    clean_linguistic_ratio_pct: number;
  };
  stage5: {
    overall_status: string;
    overall_status_hi: string;
    total_words: number;
    flagged_words_count: number;
    accuracy_statement: string;
    line_warnings: string[];
    stage_summary: Record<string, any>;
  };
}

export interface PageData {
  id: string;
  document_id: string;
  page_number: number;
  original_image_path: string;
  preprocessed_image_path: string;
  quality_metrics: QualityMetrics;
  raw_ocr_text: string;
  original_ocr_text?: string;
  verified_text: string;
  reviewed_text?: string;
  confirmed_text?: string;
  word_tokens: WordToken[];
  stage_metrics: StageMetrics;
  status: string;
  error_code?: string;
  error_message?: string;
  retry_count?: number;
  provenance?: Record<string, any>;
}

export interface DocumentData {
  id: string;
  title: string;
  original_filename: string;
  file_type: 'image' | 'pdf';
  total_pages: number;
  processed_pages: number;
  status: string;
  verification_status: string;
  collection_name: string;
  created_at: string;
  updated_at: string;
  preview_text?: string;
  provenance?: Record<string, any>;
}

export interface UnresolvedPageInfo {
  page_number: number;
  status: string;
  error_code: string;
  error_message: string;
  retry_count: number;
  flagged_tokens_count: number;
}

export interface CorrectionLog {
  id: number;
  document_id: string;
  page_number: number;
  word_index: number;
  original_text: string;
  corrected_text: string;
  reason: string;
  timestamp: string;
}

export interface BenchmarkCase {
  id: string;
  title: string;
  genre: string;
  difficulty: string;
  ground_truth: string;
  notes: string;
}

