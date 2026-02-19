/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DependentCreate } from '../models/DependentCreate';
import type { DependentResponse } from '../models/DependentResponse';
import type { DependentUpdate } from '../models/DependentUpdate';
import type { FamilyOverviewResponse } from '../models/FamilyOverviewResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DependentsService {
    /**
     * List Dependents
     * List all dependents for the current user.
     * @returns DependentResponse Successful Response
     * @throws ApiError
     */
    public static listDependentsApiV1DependentsGet(): CancelablePromise<Array<DependentResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/dependents',
        });
    }
    /**
     * Create Dependent
     * Add a new dependent.
     * @param requestBody
     * @returns DependentResponse Successful Response
     * @throws ApiError
     */
    public static createDependentApiV1DependentsPost(
        requestBody: DependentCreate,
    ): CancelablePromise<DependentResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/dependents',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Dependent
     * Get a specific dependent's details.
     * @param dependentId
     * @returns DependentResponse Successful Response
     * @throws ApiError
     */
    public static getDependentApiV1DependentsDependentIdGet(
        dependentId: number,
    ): CancelablePromise<DependentResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/dependents/{dependent_id}',
            path: {
                'dependent_id': dependentId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Dependent
     * Update a dependent's information.
     * @param dependentId
     * @param requestBody
     * @returns DependentResponse Successful Response
     * @throws ApiError
     */
    public static updateDependentApiV1DependentsDependentIdPut(
        dependentId: number,
        requestBody: DependentUpdate,
    ): CancelablePromise<DependentResponse> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/dependents/{dependent_id}',
            path: {
                'dependent_id': dependentId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Remove Dependent
     * Remove a dependent (unlinks relationship, doesn't delete data).
     * @param dependentId
     * @returns void
     * @throws ApiError
     */
    public static removeDependentApiV1DependentsDependentIdDelete(
        dependentId: number,
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/dependents/{dependent_id}',
            path: {
                'dependent_id': dependentId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Family Overview
     * Get overview of all family members including self and dependents.
     * @returns FamilyOverviewResponse Successful Response
     * @throws ApiError
     */
    public static getFamilyOverviewApiV1DependentsFamilyOverviewGet(): CancelablePromise<FamilyOverviewResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/dependents/family/overview',
        });
    }
}
