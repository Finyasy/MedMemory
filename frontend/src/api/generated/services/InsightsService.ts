/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PatientInsightsResponse } from '../models/PatientInsightsResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class InsightsService {
    /**
     * Get Patient Insights
     * Return lightweight lab/medication insights for dashboards.
     * @param patientId
     * @returns PatientInsightsResponse Successful Response
     * @throws ApiError
     */
    public static getPatientInsightsApiV1InsightsPatientPatientIdGet(
        patientId: number,
    ): CancelablePromise<PatientInsightsResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/insights/patient/{patient_id}',
            path: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
