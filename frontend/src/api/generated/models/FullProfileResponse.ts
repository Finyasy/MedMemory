/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AllergyResponse } from './AllergyResponse';
import type { ConditionResponse } from './ConditionResponse';
import type { EmergencyContactResponse } from './EmergencyContactResponse';
import type { EmergencyInfoResponse } from './EmergencyInfoResponse';
import type { FamilyHistoryResponse } from './FamilyHistoryResponse';
import type { GrowthMeasurementResponse } from './GrowthMeasurementResponse';
import type { InsuranceResponse } from './InsuranceResponse';
import type { LifestyleResponse } from './LifestyleResponse';
import type { ProfileCompletionStatus } from './ProfileCompletionStatus';
import type { ProviderResponse } from './ProviderResponse';
import type { VaccinationResponse } from './VaccinationResponse';
export type FullProfileResponse = {
    id: number;
    first_name: string;
    last_name: string;
    full_name: string;
    date_of_birth: (string | null);
    age: (number | null);
    sex: (string | null);
    gender: (string | null);
    blood_type: (string | null);
    height_cm: (string | null);
    weight_kg: (string | null);
    phone: (string | null);
    email: (string | null);
    address: (string | null);
    preferred_language: (string | null);
    timezone: (string | null);
    profile_photo_url: (string | null);
    is_dependent: boolean;
    profile_completed_at: (string | null);
    emergency_info?: (EmergencyInfoResponse | null);
    emergency_contacts?: Array<EmergencyContactResponse>;
    allergies?: Array<AllergyResponse>;
    conditions?: Array<ConditionResponse>;
    providers?: Array<ProviderResponse>;
    lifestyle?: (LifestyleResponse | null);
    insurance?: Array<InsuranceResponse>;
    family_history?: Array<FamilyHistoryResponse>;
    vaccinations?: Array<VaccinationResponse>;
    growth_measurements?: Array<GrowthMeasurementResponse>;
    profile_completion?: (ProfileCompletionStatus | null);
};

