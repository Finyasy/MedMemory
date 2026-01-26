/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Response schema for a memory chunk.
 */
export type MemoryChunkResponse = {
    id: number;
    patient_id: number;
    content: string;
    source_type: string;
    source_id?: (number | null);
    source_table?: (string | null);
    chunk_index?: number;
    page_number?: (number | null);
    context_date?: (string | null);
    chunk_type?: (string | null);
    importance_score?: (number | null);
    is_indexed: boolean;
    indexed_at?: (string | null);
    created_at: string;
};

