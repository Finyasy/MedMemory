/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * OCR refinement output for a document.
 */
export type OcrRefinementResponse = {
    document_id: number;
    ocr_language?: (string | null);
    ocr_confidence?: (number | null);
    ocr_text_raw?: (string | null);
    ocr_text_cleaned?: (string | null);
    ocr_entities?: Record<string, any>;
    used_ocr?: boolean;
};

