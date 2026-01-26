/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { QuickSearchResult } from './QuickSearchResult';
/**
 * Quick search response.
 */
export type QuickSearchResponse = {
    query: string;
    results: Array<QuickSearchResult>;
    total_results: number;
    search_time_ms: number;
};

