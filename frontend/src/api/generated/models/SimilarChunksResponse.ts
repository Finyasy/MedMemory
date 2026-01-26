/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SearchResultItem } from './SearchResultItem';
/**
 * Response with similar chunks.
 */
export type SimilarChunksResponse = {
    source_chunk_id: number;
    similar_chunks: Array<SearchResultItem>;
};

