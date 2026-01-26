/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EncounterIngest } from './EncounterIngest';
import type { LabResultIngest } from './LabResultIngest';
import type { MedicationIngest } from './MedicationIngest';
/**
 * Request for batch ingestion of multiple record types.
 */
export type BatchIngestionRequest = {
    labs?: (Array<LabResultIngest> | null);
    medications?: (Array<MedicationIngest> | null);
    encounters?: (Array<EncounterIngest> | null);
};

