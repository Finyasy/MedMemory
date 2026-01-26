/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LocalizationBox } from './LocalizationBox';
/**
 * Response from localization endpoint.
 */
export type LocalizationResponse = {
    answer: string;
    boxes?: Array<LocalizationBox>;
    image_width: number;
    image_height: number;
    tokens_input?: number;
    tokens_generated?: number;
    tokens_total?: number;
    generation_time_ms?: number;
};

