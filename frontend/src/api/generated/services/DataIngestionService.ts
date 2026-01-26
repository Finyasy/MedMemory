/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { BatchIngestionRequest } from '../models/BatchIngestionRequest';
import type { EncounterIngest } from '../models/EncounterIngest';
import type { EncounterResponse } from '../models/EncounterResponse';
import type { IngestionResultResponse } from '../models/IngestionResultResponse';
import type { LabPanelIngest } from '../models/LabPanelIngest';
import type { LabResultIngest } from '../models/LabResultIngest';
import type { LabResultResponse } from '../models/LabResultResponse';
import type { MedicationIngest } from '../models/MedicationIngest';
import type { MedicationResponse } from '../models/MedicationResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DataIngestionService {
    /**
     * Ingest Lab Result
     * Ingest a single lab result.
     * @param requestBody
     * @returns LabResultResponse Successful Response
     * @throws ApiError
     */
    public static ingestLabResultApiV1IngestLabsPost(
        requestBody: LabResultIngest,
    ): CancelablePromise<LabResultResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/ingest/labs',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Ingest Lab Results Batch
     * Ingest multiple lab results in a batch.
     * @param requestBody
     * @returns IngestionResultResponse Successful Response
     * @throws ApiError
     */
    public static ingestLabResultsBatchApiV1IngestLabsBatchPost(
        requestBody: Array<LabResultIngest>,
    ): CancelablePromise<IngestionResultResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/ingest/labs/batch',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Ingest Lab Panel
     * Ingest a complete lab panel (multiple related tests).
     * @param requestBody
     * @returns LabResultResponse Successful Response
     * @throws ApiError
     */
    public static ingestLabPanelApiV1IngestLabsPanelPost(
        requestBody: LabPanelIngest,
    ): CancelablePromise<Array<LabResultResponse>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/ingest/labs/panel',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Ingest Medication
     * Ingest a single medication/prescription.
     * @param requestBody
     * @returns MedicationResponse Successful Response
     * @throws ApiError
     */
    public static ingestMedicationApiV1IngestMedicationsPost(
        requestBody: MedicationIngest,
    ): CancelablePromise<MedicationResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/ingest/medications',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Ingest Medications Batch
     * Ingest multiple medications in a batch.
     * @param requestBody
     * @returns IngestionResultResponse Successful Response
     * @throws ApiError
     */
    public static ingestMedicationsBatchApiV1IngestMedicationsBatchPost(
        requestBody: Array<MedicationIngest>,
    ): CancelablePromise<IngestionResultResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/ingest/medications/batch',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Discontinue Medication
     * Discontinue an active medication.
     * @param medicationId
     * @param reason
     * @returns MedicationResponse Successful Response
     * @throws ApiError
     */
    public static discontinueMedicationApiV1IngestMedicationsMedicationIdDiscontinuePost(
        medicationId: number,
        reason?: (string | null),
    ): CancelablePromise<MedicationResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/ingest/medications/{medication_id}/discontinue',
            path: {
                'medication_id': medicationId,
            },
            query: {
                'reason': reason,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Ingest Encounter
     * Ingest a single medical encounter/visit.
     * @param requestBody
     * @returns EncounterResponse Successful Response
     * @throws ApiError
     */
    public static ingestEncounterApiV1IngestEncountersPost(
        requestBody: EncounterIngest,
    ): CancelablePromise<EncounterResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/ingest/encounters',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Ingest Encounters Batch
     * Ingest multiple encounters in a batch.
     * @param requestBody
     * @returns IngestionResultResponse Successful Response
     * @throws ApiError
     */
    public static ingestEncountersBatchApiV1IngestEncountersBatchPost(
        requestBody: Array<EncounterIngest>,
    ): CancelablePromise<IngestionResultResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/ingest/encounters/batch',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Ingest Batch
     * Ingest multiple record types in a single request.
     *
     * This endpoint allows you to ingest labs, medications, and encounters
     * all at once, which is useful for importing data from EHR exports.
     * @param requestBody
     * @returns any Successful Response
     * @throws ApiError
     */
    public static ingestBatchApiV1IngestBatchPost(
        requestBody: BatchIngestionRequest,
    ): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/ingest/batch',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
