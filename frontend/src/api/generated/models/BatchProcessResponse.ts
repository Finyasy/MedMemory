/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Response for batch document processing.
 */
export type BatchProcessResponse = {
    total: number;
    processed: number;
    failed: number;
    errors?: Array<string>;
};

