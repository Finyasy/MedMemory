/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Response schema for document.
 */
export type DocumentResponse = {
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
};

