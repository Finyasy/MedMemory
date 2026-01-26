/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { InsightsLabItem } from './InsightsLabItem';
import type { InsightsMedicationItem } from './InsightsMedicationItem';
export type PatientInsightsResponse = {
    patient_id: number;
    lab_total: number;
    lab_abnormal: number;
    recent_labs: Array<InsightsLabItem>;
    active_medications: number;
    recent_medications: Array<InsightsMedicationItem>;
    a1c_series: Array<number>;
};

