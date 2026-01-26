/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Response after document processing.
 */
export type DocumentProcessResponse = {
    document_id: number;
    status: string;
    page_count?: (number | null);
    chunks_created?: number;
    /**
     * First 500 chars of extracted text
     */
    text_preview?: (string | null);
};

