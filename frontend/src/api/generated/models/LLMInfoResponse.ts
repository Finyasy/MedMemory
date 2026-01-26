/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Information about the loaded LLM.
 */
export type LLMInfoResponse = {
    model_name: string;
    device: string;
    max_new_tokens: number;
    temperature: number;
    vocab_size?: (number | null);
    is_loaded: boolean;
};

