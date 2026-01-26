/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * A single search result.
 */
export type SearchResultItem = {
    chunk_id: number;
    patient_id: number;
    content: string;
    source_type: string;
    source_id?: (number | null);
    similarity_score: number;
    context_date?: (string | null);
    chunk_type?: (string | null);
};

