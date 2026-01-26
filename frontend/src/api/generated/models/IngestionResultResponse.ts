/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Response for ingestion operations.
 */
export type IngestionResultResponse = {
    success: boolean;
    records_created?: number;
    records_updated?: number;
    records_skipped?: number;
    errors?: Array<string>;
    timestamp: string;
};

