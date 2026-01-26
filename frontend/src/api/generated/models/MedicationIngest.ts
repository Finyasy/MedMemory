/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Schema for ingesting a medication/prescription.
 */
export type MedicationIngest = {
    patient_id?: (number | null);
    patient_external_id?: (string | null);
    patient_first_name?: (string | null);
    patient_last_name?: (string | null);
    name: string;
    generic_name?: (string | null);
    drug_code?: (string | null);
    drug_class?: (string | null);
    dosage?: (string | null);
    dosage_value?: (number | null);
    dosage_unit?: (string | null);
    frequency?: (string | null);
    route?: (string | null);
    start_date?: (string | null);
    end_date?: (string | null);
    prescribed_at?: (string | null);
    is_active?: (boolean | null);
    status?: (string | null);
    discontinue_reason?: (string | null);
    prescriber?: (string | null);
    pharmacy?: (string | null);
    quantity?: (number | null);
    refills_remaining?: (number | null);
    indication?: (string | null);
    instructions?: (string | null);
    notes?: (string | null);
    source_system?: (string | null);
    source_id?: (string | null);
};

