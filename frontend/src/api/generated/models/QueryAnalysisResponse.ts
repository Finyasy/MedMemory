/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TemporalContextSchema } from './TemporalContextSchema';
/**
 * Response schema for query analysis.
 */
export type QueryAnalysisResponse = {
    original_query: string;
    normalized_query: string;
    intent: string;
    confidence: number;
    medical_entities?: Array<string>;
    medication_names?: Array<string>;
    test_names?: Array<string>;
    condition_names?: Array<string>;
    temporal: TemporalContextSchema;
    data_sources?: Array<string>;
    keywords?: Array<string>;
    use_semantic_search?: boolean;
    use_keyword_search?: boolean;
    boost_recent?: boolean;
};

