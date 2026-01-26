/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Response schema for medication.
 */
export type MedicationResponse = {
    id: number;
    patient_id: number;
    name: string;
    generic_name?: (string | null);
    drug_class?: (string | null);
    dosage?: (string | null);
    frequency?: (string | null);
    route?: (string | null);
    start_date?: (string | null);
    end_date?: (string | null);
    is_active: boolean;
    status?: (string | null);
    prescriber?: (string | null);
    indication?: (string | null);
    created_at: string;
};

