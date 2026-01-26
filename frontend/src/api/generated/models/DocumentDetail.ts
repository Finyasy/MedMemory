/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Detailed document response including extracted text.
 */
export type DocumentDetail = {
    id: number;
    patient_id: number;
    filename: string;
    original_filename: string;
    file_size?: (number | null);
    mime_type?: (string | null);
    document_type: string;
    category?: (string | null);
    title?: (string | null);
    description?: (string | null);
    document_date?: (string | null);
    received_date: string;
    processing_status: string;
    is_processed: boolean;
    processed_at?: (string | null);
    page_count?: (number | null);
    created_at: string;
    extracted_text?: (string | null);
    processing_error?: (string | null);
    ocr_confidence?: (number | null);
    ocr_language?: (string | null);
    ocr_text_raw?: (string | null);
    ocr_text_cleaned?: (string | null);
    ocr_entities?: (string | null);
    author?: (string | null);
    facility?: (string | null);
};

