/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * A re-ranked result.
 */
export type RankedResultItem = {
    id: number;
    content: string;
    source_type: string;
    source_id?: (number | null);
    context_date?: (string | null);
    final_score: number;
    relevance_score: number;
    diversity_penalty: number;
    reasoning?: string;
};

