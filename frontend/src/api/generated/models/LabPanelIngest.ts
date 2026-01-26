/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LabResultIngest } from './LabResultIngest';
/**
 * Schema for ingesting a lab panel (multiple tests).
 */
export type LabPanelIngest = {
    patient_id: number;
    panel_name: string;
    collected_at?: (string | null);
    ordering_provider?: (string | null);
    results: Array<LabResultIngest>;
};

