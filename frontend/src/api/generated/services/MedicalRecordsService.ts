/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RecordCreate } from '../models/RecordCreate';
import type { RecordResponse } from '../models/RecordResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class MedicalRecordsService {
    /**
     * List Records
     * List all medical records with optional filtering.
     * @param patientId Filter by patient ID
     * @param recordType Filter by record type
     * @param skip
     * @param limit
     * @returns RecordResponse Successful Response
     * @throws ApiError
     */
    public static listRecordsApiV1RecordsGet(
        patientId?: (number | null),
        recordType?: (string | null),
        skip?: number,
        limit: number = 100,
    ): CancelablePromise<Array<RecordResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/records/',
            query: {
                'patient_id': patientId,
                'record_type': recordType,
                'skip': skip,
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Record
     * Create a new medical record.
     * @param patientId Patient ID for this record
     * @param requestBody
     * @returns RecordResponse Successful Response
     * @throws ApiError
     */
    public static createRecordApiV1RecordsPost(
        patientId: number,
        requestBody: RecordCreate,
    ): CancelablePromise<RecordResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/records/',
            query: {
                'patient_id': patientId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Record
     * Get a specific medical record by ID.
     * @param recordId
     * @returns RecordResponse Successful Response
     * @throws ApiError
     */
    public static getRecordApiV1RecordsRecordIdGet(
        recordId: number,
    ): CancelablePromise<RecordResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/records/{record_id}',
            path: {
                'record_id': recordId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Record
     * Delete a medical record.
     * @param recordId
     * @returns void
     * @throws ApiError
     */
    public static deleteRecordApiV1RecordsRecordIdDelete(
        recordId: number,
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/records/{record_id}',
            path: {
                'record_id': recordId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
