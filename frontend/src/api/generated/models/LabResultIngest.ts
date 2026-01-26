/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Schema for ingesting a single lab result.
 */
export type LabResultIngest = {
    patient_id?: (number | null);
    patient_external_id?: (string | null);
    patient_first_name?: (string | null);
    patient_last_name?: (string | null);
    test_name: string;
    test_code?: (string | null);
    category?: (string | null);
    value?: (string | null);
    numeric_value?: (number | null);
    unit?: (string | null);
    reference_range?: (string | null);
    status?: (string | null);
    collected_at?: (string | null);
    resulted_at?: (string | null);
    notes?: (string | null);
    ordering_provider?: (string | null);
    performing_lab?: (string | null);
    source_system?: (string | null);
    source_id?: (string | null);
};

