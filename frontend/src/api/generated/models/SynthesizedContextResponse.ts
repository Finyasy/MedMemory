/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ContextSectionSchema } from './ContextSectionSchema';
/**
 * Synthesized context response.
 */
export type SynthesizedContextResponse = {
    query: string;
    sections?: Array<ContextSectionSchema>;
    full_context: string;
    total_chunks_used?: number;
    total_characters?: number;
    estimated_tokens?: number;
    source_types_included?: Array<string>;
    earliest_date?: (string | null);
    latest_date?: (string | null);
};

