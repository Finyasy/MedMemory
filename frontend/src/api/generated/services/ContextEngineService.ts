/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { app__schemas__context__ContextRequest } from '../models/app__schemas__context__ContextRequest';
import type { app__schemas__context__ContextResponse } from '../models/app__schemas__context__ContextResponse';
import type { QueryAnalysisResponse } from '../models/QueryAnalysisResponse';
import type { QuickSearchRequest } from '../models/QuickSearchRequest';
import type { QuickSearchResponse } from '../models/QuickSearchResponse';
import type { SimpleContextRequest } from '../models/SimpleContextRequest';
import type { SimpleContextResponse } from '../models/SimpleContextResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class ContextEngineService {
    /**
     * Get Context
     * Get optimized context for answering a medical question.
     *
     * This is the main entry point for the context engine. It:
     * 1. Analyzes the query to understand intent
     * 2. Retrieves relevant content using hybrid search
     * 3. Ranks and filters results
     * 4. Synthesizes context for LLM consumption
     *
     * The response includes detailed information about each step
     * for transparency and debugging.
     * @param requestBody
     * @returns app__schemas__context__ContextResponse Successful Response
     * @throws ApiError
     */
    public static getContextApiV1ContextPost(
        requestBody: app__schemas__context__ContextRequest,
    ): CancelablePromise<app__schemas__context__ContextResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/context/',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Simple Context
     * Get simplified context for LLM consumption.
     *
     * A simpler endpoint that returns just the essentials:
     * - The synthesized context
     * - The complete prompt
     * - Basic metadata
     *
     * Use this for direct LLM integration.
     * @param requestBody
     * @returns SimpleContextResponse Successful Response
     * @throws ApiError
     */
    public static getSimpleContextApiV1ContextSimplePost(
        requestBody: SimpleContextRequest,
    ): CancelablePromise<SimpleContextResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/context/simple',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Analyze Query
     * Analyze a query without retrieval.
     *
     * Useful for understanding how the context engine interprets queries.
     * @param query
     * @returns QueryAnalysisResponse Successful Response
     * @throws ApiError
     */
    public static analyzeQueryApiV1ContextAnalyzePost(
        query: string,
    ): CancelablePromise<QueryAnalysisResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/context/analyze',
            query: {
                'query': query,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Quick Search
     * Quick hybrid search without full context synthesis.
     *
     * Faster than full context retrieval. Returns ranked results
     * without building the complete LLM prompt.
     * @param requestBody
     * @returns QuickSearchResponse Successful Response
     * @throws ApiError
     */
    public static quickSearchApiV1ContextSearchPost(
        requestBody: QuickSearchRequest,
    ): CancelablePromise<QuickSearchResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/context/search',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Generate Prompt
     * Generate an LLM-ready prompt for a patient question.
     *
     * Returns just the prompt string, ready to send to an LLM.
     * @param patientId
     * @param question
     * @param maxTokens
     * @param systemPrompt
     * @returns any Successful Response
     * @throws ApiError
     */
    public static generatePromptApiV1ContextPromptPatientPatientIdGet(
        patientId: number,
        question: string,
        maxTokens: number = 4000,
        systemPrompt?: (string | null),
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/context/prompt/patient/{patient_id}',
            path: {
                'patient_id': patientId,
            },
            query: {
                'question': question,
                'max_tokens': maxTokens,
                'system_prompt': systemPrompt,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
