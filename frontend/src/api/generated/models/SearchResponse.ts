/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SearchResultItem } from './SearchResultItem';
/**
 * Response schema for semantic search.
 */
export type SearchResponse = {
    query: string;
    results: Array<SearchResultItem>;
    total_results: number;
    search_time_ms: number;
};

