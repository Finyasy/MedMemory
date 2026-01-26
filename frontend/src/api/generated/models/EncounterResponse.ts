/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Response schema for encounter.
 */
export type EncounterResponse = {
    id: number;
    patient_id: number;
    encounter_type: string;
    encounter_date: string;
    provider_name?: (string | null);
    provider_specialty?: (string | null);
    facility?: (string | null);
    chief_complaint?: (string | null);
    assessment?: (string | null);
    plan?: (string | null);
    status: string;
    vital_blood_pressure?: (string | null);
    vital_heart_rate?: (number | null);
    vital_temperature?: (number | null);
    created_at: string;
};

