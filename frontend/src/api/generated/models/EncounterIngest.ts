/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { VitalsIngest } from './VitalsIngest';
/**
 * Schema for ingesting a medical encounter/visit.
 */
export type EncounterIngest = {
    patient_id?: (number | null);
    patient_external_id?: (string | null);
    patient_first_name?: (string | null);
    patient_last_name?: (string | null);
    encounter_type?: string;
    encounter_date: string;
    start_time?: (string | null);
    end_time?: (string | null);
    facility?: (string | null);
    department?: (string | null);
    location?: (string | null);
    provider_name?: (string | null);
    provider_specialty?: (string | null);
    chief_complaint?: (string | null);
    reason_for_visit?: (string | null);
    subjective?: (string | null);
    objective?: (string | null);
    assessment?: (string | null);
    plan?: (string | null);
    follow_up?: (string | null);
    clinical_notes?: (string | null);
    diagnoses?: (Array<string> | null);
    vitals?: (VitalsIngest | null);
    status?: (string | null);
    source_system?: (string | null);
    source_id?: (string | null);
};

