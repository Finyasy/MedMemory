/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Request to get context for a question.
 */
export type app__schemas__context__ContextRequest = {
    query: string;
    patient_id: number;
    max_results?: (number | null);
    max_tokens?: (number | null);
    min_score?: number;
    system_prompt?: (string | null);
};

