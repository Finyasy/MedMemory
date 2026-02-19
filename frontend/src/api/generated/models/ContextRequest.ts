/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Request to get context for a question.
 */
export type ContextRequest = {
    patient_id: number;
    question: string;
    max_chunks?: number;
    max_tokens?: number;
};

