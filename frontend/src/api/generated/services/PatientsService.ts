/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PatientCreate } from '../models/PatientCreate';
import type { PatientResponse } from '../models/PatientResponse';
import type { PatientSummary } from '../models/PatientSummary';
import type { PatientUpdate } from '../models/PatientUpdate';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class PatientsService {
    /**
     * List Patients
     * List all patients with optional search.
     * @param skip
     * @param limit
     * @param search
     * @returns PatientSummary Successful Response
     * @throws ApiError
     */
    public static listPatientsApiV1PatientsGet(
        skip?: number,
        limit: number = 100,
        search?: (string | null),
    ): CancelablePromise<Array<PatientSummary>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/patients/',
            query: {
                'skip': skip,
                'limit': limit,
                'search': search,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Patient
     * Create a new patient.
     * @param requestBody
     * @returns PatientResponse Successful Response
     * @throws ApiError
     */
    public static createPatientApiV1PatientsPost(
        requestBody: PatientCreate,
    ): CancelablePromise<PatientResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/patients/',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Patient
     * Get a specific patient by ID.
     * @param patientId
     * @returns PatientResponse Successful Response
     * @throws ApiError
     */
    public static getPatientApiV1PatientsPatientIdGet(
        patientId: number,
    ): CancelablePromise<PatientResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/patients/{patient_id}',
            path: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Patient
     * Update a patient's information.
     * @param patientId
     * @param requestBody
     * @returns PatientResponse Successful Response
     * @throws ApiError
     */
    public static updatePatientApiV1PatientsPatientIdPatch(
        patientId: number,
        requestBody: PatientUpdate,
    ): CancelablePromise<PatientResponse> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/api/v1/patients/{patient_id}',
            path: {
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
     * Delete Patient
     * Delete a patient and all associated records.
     * @param patientId
     * @returns void
     * @throws ApiError
     */
    public static deletePatientApiV1PatientsPatientIdDelete(
        patientId: number,
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/patients/{patient_id}',
            path: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
