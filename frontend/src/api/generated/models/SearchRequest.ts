/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Request schema for semantic search.
 */
export type SearchRequest = {
    query: string;
    patient_id?: (number | null);
    /**
     * Filter by source types: lab_result, medication, encounter, document
     */
    source_types?: (Array<string> | null);
    limit?: number;
    min_similarity?: number;
    date_from?: (string | null);
    date_to?: (string | null);
};

