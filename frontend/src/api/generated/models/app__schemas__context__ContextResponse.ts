/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { QueryAnalysisResponse } from './QueryAnalysisResponse';
import type { RankedResultItem } from './RankedResultItem';
import type { RetrievalStatsResponse } from './RetrievalStatsResponse';
import type { SynthesizedContextResponse } from './SynthesizedContextResponse';
/**
 * Complete context engine response.
 */
export type app__schemas__context__ContextResponse = {
    query_analysis: QueryAnalysisResponse;
    retrieval_stats: RetrievalStatsResponse;
    ranked_results: Array<RankedResultItem>;
    synthesized_context: SynthesizedContextResponse;
    prompt: string;
    analysis_time_ms: number;
    retrieval_time_ms: number;
    ranking_time_ms: number;
    synthesis_time_ms: number;
    total_time_ms: number;
};

