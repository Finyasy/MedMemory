/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LLMInfoResponse } from '../models/LLMInfoResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class HealthService {
    /**
     * Health Check
     * Health check endpoint for Docker and load balancers.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static healthCheckHealthGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/health',
        });
    }
    /**
     * Root
     * Root endpoint with API information.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static rootGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/',
        });
    }
    /**
     * Get Llm Info
     * Get information about the loaded LLM model.
     *
     * This endpoint is public and does not require authentication
     * as it only returns informational metadata about the LLM configuration.
     * @returns LLMInfoResponse Successful Response
     * @throws ApiError
     */
    public static getLlmInfoLlmInfoGet(): CancelablePromise<LLMInfoResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/llm/info',
        });
    }
    /**
     * Llm Health
     * Lightweight LLM health endpoint for frontend checks.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static llmHealthHealthLlmGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/health/llm',
        });
    }
}
