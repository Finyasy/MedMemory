/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ContextRequest } from '../models/ContextRequest';
import type { ContextResponse } from '../models/ContextResponse';
import type { IndexingStatsResponse } from '../models/IndexingStatsResponse';
import type { IndexTextRequest } from '../models/IndexTextRequest';
import type { MemoryChunkResponse } from '../models/MemoryChunkResponse';
import type { MemoryStatsResponse } from '../models/MemoryStatsResponse';
import type { SearchRequest } from '../models/SearchRequest';
import type { SearchResponse } from '../models/SearchResponse';
import type { SimilarChunksRequest } from '../models/SimilarChunksRequest';
import type { SimilarChunksResponse } from '../models/SimilarChunksResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class MemorySearchService {
    /**
     * Semantic Search
     * Perform semantic search over the medical memory.
     *
     * Finds relevant medical information based on natural language queries.
     * Uses vector similarity to match queries against indexed medical records.
     *
     * Examples:
     * - "What are the patient's current medications?"
     * - "Any abnormal lab results in the past year?"
     * - "History of cardiac conditions"
     * @param requestBody
     * @returns SearchResponse Successful Response
     * @throws ApiError
     */
    public static semanticSearchApiV1MemorySearchPost(
        requestBody: SearchRequest,
    ): CancelablePromise<SearchResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/memory/search',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Search Patient History
     * Search within a specific patient's medical history.
     *
     * Convenient endpoint for patient-specific searches.
     * @param patientId
     * @param query
     * @param limit
     * @param minSimilarity
     * @returns SearchResponse Successful Response
     * @throws ApiError
     */
    public static searchPatientHistoryApiV1MemorySearchPatientPatientIdGet(
        patientId: number,
        query: string,
        limit: number = 10,
        minSimilarity: number = 0.3,
    ): CancelablePromise<SearchResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/memory/search/patient/{patient_id}',
            path: {
                'patient_id': patientId,
            },
            query: {
                'query': query,
                'limit': limit,
                'min_similarity': minSimilarity,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Context For Question
     * Get relevant context for answering a question.
     *
     * Returns concatenated relevant chunks optimized for feeding into an LLM.
     * Useful for RAG (Retrieval-Augmented Generation) workflows.
     * @param requestBody
     * @returns ContextResponse Successful Response
     * @throws ApiError
     */
    public static getContextForQuestionApiV1MemoryContextPost(
        requestBody: ContextRequest,
    ): CancelablePromise<ContextResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/memory/context',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Find Similar Chunks
     * Find chunks similar to a given chunk.
     *
     * Useful for finding related information or expanding context.
     * @param requestBody
     * @returns SimilarChunksResponse Successful Response
     * @throws ApiError
     */
    public static findSimilarChunksApiV1MemorySimilarPost(
        requestBody: SimilarChunksRequest,
    ): CancelablePromise<SimilarChunksResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/memory/similar',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Index Custom Text
     * Index custom text content into memory.
     *
     * Useful for adding notes, summaries, or other text that
     * isn't part of standard medical records.
     * @param requestBody
     * @returns IndexingStatsResponse Successful Response
     * @throws ApiError
     */
    public static indexCustomTextApiV1MemoryIndexTextPost(
        requestBody: IndexTextRequest,
    ): CancelablePromise<IndexingStatsResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/memory/index/text',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Index Patient Records
     * Index all records for a patient.
     *
     * This indexes:
     * - Lab results
     * - Medications
     * - Encounters
     * - Processed documents
     *
     * Run this after ingesting patient data to enable semantic search.
     * @param patientId
     * @returns IndexingStatsResponse Successful Response
     * @throws ApiError
     */
    public static indexPatientRecordsApiV1MemoryIndexPatientPatientIdPost(
        patientId: number,
    ): CancelablePromise<IndexingStatsResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/memory/index/patient/{patient_id}',
            path: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Reindex Chunk
     * Re-generate embedding for a specific chunk.
     * @param chunkId
     * @returns MemoryChunkResponse Successful Response
     * @throws ApiError
     */
    public static reindexChunkApiV1MemoryReindexChunkChunkIdPost(
        chunkId: number,
    ): CancelablePromise<MemoryChunkResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/memory/reindex/chunk/{chunk_id}',
            path: {
                'chunk_id': chunkId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Memory Chunks
     * List memory chunks with optional filtering.
     * @param patientId
     * @param sourceType
     * @param indexedOnly
     * @param skip
     * @param limit
     * @returns MemoryChunkResponse Successful Response
     * @throws ApiError
     */
    public static listMemoryChunksApiV1MemoryChunksGet(
        patientId?: (number | null),
        sourceType?: (string | null),
        indexedOnly: boolean = true,
        skip?: number,
        limit: number = 100,
    ): CancelablePromise<Array<MemoryChunkResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/memory/chunks',
            query: {
                'patient_id': patientId,
                'source_type': sourceType,
                'indexed_only': indexedOnly,
                'skip': skip,
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Memory Chunk
     * Get a specific memory chunk.
     * @param chunkId
     * @returns MemoryChunkResponse Successful Response
     * @throws ApiError
     */
    public static getMemoryChunkApiV1MemoryChunksChunkIdGet(
        chunkId: number,
    ): CancelablePromise<MemoryChunkResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/memory/chunks/{chunk_id}',
            path: {
                'chunk_id': chunkId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Memory Chunk
     * Delete a specific memory chunk.
     * @param chunkId
     * @returns void
     * @throws ApiError
     */
    public static deleteMemoryChunkApiV1MemoryChunksChunkIdDelete(
        chunkId: number,
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/memory/chunks/{chunk_id}',
            path: {
                'chunk_id': chunkId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Patient Memory
     * Delete all memory chunks for a patient.
     *
     * Warning: This is irreversible. You'll need to re-index the patient's data.
     * @param patientId
     * @returns any Successful Response
     * @throws ApiError
     */
    public static deletePatientMemoryApiV1MemoryPatientPatientIdMemoryDelete(
        patientId: number,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/memory/patient/{patient_id}/memory',
            path: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Memory Stats
     * Get statistics about indexed memory.
     * @param patientId
     * @returns MemoryStatsResponse Successful Response
     * @throws ApiError
     */
    public static getMemoryStatsApiV1MemoryStatsGet(
        patientId?: (number | null),
    ): CancelablePromise<MemoryStatsResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/memory/stats',
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Embedding Info
     * Get information about the embedding model.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getEmbeddingInfoApiV1MemoryEmbeddingInfoGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/memory/embedding/info',
        });
    }
}
