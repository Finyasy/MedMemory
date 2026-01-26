/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Response from volume interpretation.
 */
export type VolumeChatResponse = {
    answer: string;
    total_slices: number;
    sampled_indices?: Array<number>;
    grid_rows: number;
    grid_cols: number;
    tile_size: number;
    tokens_input?: number;
    tokens_generated?: number;
    tokens_total?: number;
    generation_time_ms?: number;
};

