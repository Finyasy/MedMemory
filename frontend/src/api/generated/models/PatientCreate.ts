/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Schema for creating a new patient.
 */
export type PatientCreate = {
    first_name: string;
    last_name: string;
    date_of_birth?: (string | null);
    gender?: (string | null);
    email?: (string | null);
    phone?: (string | null);
    address?: (string | null);
    blood_type?: (string | null);
    allergies?: (string | null);
    medical_conditions?: (string | null);
    external_id?: (string | null);
};

