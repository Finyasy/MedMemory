/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Response schema for lab result.
 */
export type LabResultResponse = {
    id: number;
    patient_id: number;
    test_name: string;
    test_code?: (string | null);
    category?: (string | null);
    value?: (string | null);
    numeric_value?: (number | null);
    unit?: (string | null);
    reference_range?: (string | null);
    status?: (string | null);
    is_abnormal: boolean;
    collected_at?: (string | null);
    resulted_at?: (string | null);
    created_at: string;
};

