/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Request to chat with the AI.
 */
export type ChatRequest = {
    question: string;
    patient_id: number;
    conversation_id?: (string | null);
    system_prompt?: (string | null);
    max_context_tokens?: number;
    use_conversation_history?: boolean;
};

