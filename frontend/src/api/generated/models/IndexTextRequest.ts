/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Request to index custom text into memory.
 */
export type IndexTextRequest = {
    patient_id: number;
    content: string;
    source_type?: string;
    context_date?: (string | null);
    chunk_type?: (string | null);
    importance_score?: (number | null);
};

