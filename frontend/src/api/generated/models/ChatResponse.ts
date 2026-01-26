/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SourceInfo } from './SourceInfo';
/**
 * Response from chat.
 */
export type ChatResponse = {
    answer: string;
    conversation_id: string;
    message_id?: (number | null);
    num_sources?: number;
    sources?: Array<SourceInfo>;
    tokens_input?: number;
    tokens_generated?: number;
    tokens_total?: number;
    context_time_ms?: number;
    generation_time_ms?: number;
    total_time_ms?: number;
};

