/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AllergyCreate } from '../models/AllergyCreate';
import type { AllergyResponse } from '../models/AllergyResponse';
import type { AllergyUpdate } from '../models/AllergyUpdate';
import type { BasicProfileUpdate } from '../models/BasicProfileUpdate';
import type { ConditionCreate } from '../models/ConditionCreate';
import type { ConditionResponse } from '../models/ConditionResponse';
import type { ConditionUpdate } from '../models/ConditionUpdate';
import type { EmergencyContactCreate } from '../models/EmergencyContactCreate';
import type { EmergencyContactResponse } from '../models/EmergencyContactResponse';
import type { EmergencyContactUpdate } from '../models/EmergencyContactUpdate';
import type { EmergencyInfoResponse } from '../models/EmergencyInfoResponse';
import type { EmergencyInfoUpdate } from '../models/EmergencyInfoUpdate';
import type { FamilyHistoryCreate } from '../models/FamilyHistoryCreate';
import type { FamilyHistoryResponse } from '../models/FamilyHistoryResponse';
import type { FullProfileResponse } from '../models/FullProfileResponse';
import type { GrowthMeasurementCreate } from '../models/GrowthMeasurementCreate';
import type { GrowthMeasurementResponse } from '../models/GrowthMeasurementResponse';
import type { InsuranceCreate } from '../models/InsuranceCreate';
import type { InsuranceResponse } from '../models/InsuranceResponse';
import type { LifestyleResponse } from '../models/LifestyleResponse';
import type { LifestyleUpdate } from '../models/LifestyleUpdate';
import type { ProviderCreate } from '../models/ProviderCreate';
import type { ProviderResponse } from '../models/ProviderResponse';
import type { ProviderUpdate } from '../models/ProviderUpdate';
import type { VaccinationCreate } from '../models/VaccinationCreate';
import type { VaccinationResponse } from '../models/VaccinationResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class ProfileService {
    /**
     * Get Profile
     * Get complete profile for current user or specified patient.
     * @param patientId
     * @returns FullProfileResponse Successful Response
     * @throws ApiError
     */
    public static getProfileApiV1ProfileGet(
        patientId?: (number | null),
    ): CancelablePromise<FullProfileResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/profile',
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Basic Profile
     * Update basic profile information.
     * @param requestBody
     * @param patientId
     * @returns FullProfileResponse Successful Response
     * @throws ApiError
     */
    public static updateBasicProfileApiV1ProfileBasicPut(
        requestBody: BasicProfileUpdate,
        patientId?: (number | null),
    ): CancelablePromise<FullProfileResponse> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/profile/basic',
            query: {
                'patient_id': patientId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Emergency Info
     * Update emergency information.
     * @param requestBody
     * @param patientId
     * @returns EmergencyInfoResponse Successful Response
     * @throws ApiError
     */
    public static updateEmergencyInfoApiV1ProfileEmergencyPut(
        requestBody: EmergencyInfoUpdate,
        patientId?: (number | null),
    ): CancelablePromise<EmergencyInfoResponse> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/profile/emergency',
            query: {
                'patient_id': patientId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Emergency Contacts
     * List emergency contacts.
     * @param patientId
     * @returns EmergencyContactResponse Successful Response
     * @throws ApiError
     */
    public static listEmergencyContactsApiV1ProfileEmergencyContactsGet(
        patientId?: (number | null),
    ): CancelablePromise<Array<EmergencyContactResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/profile/emergency-contacts',
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Emergency Contact
     * Add an emergency contact.
     * @param requestBody
     * @param patientId
     * @returns EmergencyContactResponse Successful Response
     * @throws ApiError
     */
    public static createEmergencyContactApiV1ProfileEmergencyContactsPost(
        requestBody: EmergencyContactCreate,
        patientId?: (number | null),
    ): CancelablePromise<EmergencyContactResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/profile/emergency-contacts',
            query: {
                'patient_id': patientId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Emergency Contact
     * Update an emergency contact.
     * @param contactId
     * @param requestBody
     * @param patientId
     * @returns EmergencyContactResponse Successful Response
     * @throws ApiError
     */
    public static updateEmergencyContactApiV1ProfileEmergencyContactsContactIdPut(
        contactId: number,
        requestBody: EmergencyContactUpdate,
        patientId?: (number | null),
    ): CancelablePromise<EmergencyContactResponse> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/profile/emergency-contacts/{contact_id}',
            path: {
                'contact_id': contactId,
            },
            query: {
                'patient_id': patientId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Emergency Contact
     * Delete an emergency contact.
     * @param contactId
     * @param patientId
     * @returns void
     * @throws ApiError
     */
    public static deleteEmergencyContactApiV1ProfileEmergencyContactsContactIdDelete(
        contactId: number,
        patientId?: (number | null),
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/profile/emergency-contacts/{contact_id}',
            path: {
                'contact_id': contactId,
            },
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Allergies
     * List allergies.
     * @param patientId
     * @returns AllergyResponse Successful Response
     * @throws ApiError
     */
    public static listAllergiesApiV1ProfileAllergiesGet(
        patientId?: (number | null),
    ): CancelablePromise<Array<AllergyResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/profile/allergies',
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Allergy
     * Add an allergy.
     * @param requestBody
     * @param patientId
     * @returns AllergyResponse Successful Response
     * @throws ApiError
     */
    public static createAllergyApiV1ProfileAllergiesPost(
        requestBody: AllergyCreate,
        patientId?: (number | null),
    ): CancelablePromise<AllergyResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/profile/allergies',
            query: {
                'patient_id': patientId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Allergy
     * Update an allergy.
     * @param allergyId
     * @param requestBody
     * @param patientId
     * @returns AllergyResponse Successful Response
     * @throws ApiError
     */
    public static updateAllergyApiV1ProfileAllergiesAllergyIdPut(
        allergyId: number,
        requestBody: AllergyUpdate,
        patientId?: (number | null),
    ): CancelablePromise<AllergyResponse> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/profile/allergies/{allergy_id}',
            path: {
                'allergy_id': allergyId,
            },
            query: {
                'patient_id': patientId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Allergy
     * Delete an allergy.
     * @param allergyId
     * @param patientId
     * @returns void
     * @throws ApiError
     */
    public static deleteAllergyApiV1ProfileAllergiesAllergyIdDelete(
        allergyId: number,
        patientId?: (number | null),
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/profile/allergies/{allergy_id}',
            path: {
                'allergy_id': allergyId,
            },
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Conditions
     * List conditions.
     * @param patientId
     * @returns ConditionResponse Successful Response
     * @throws ApiError
     */
    public static listConditionsApiV1ProfileConditionsGet(
        patientId?: (number | null),
    ): CancelablePromise<Array<ConditionResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/profile/conditions',
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Condition
     * Add a condition.
     * @param requestBody
     * @param patientId
     * @returns ConditionResponse Successful Response
     * @throws ApiError
     */
    public static createConditionApiV1ProfileConditionsPost(
        requestBody: ConditionCreate,
        patientId?: (number | null),
    ): CancelablePromise<ConditionResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/profile/conditions',
            query: {
                'patient_id': patientId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Condition
     * Update a condition.
     * @param conditionId
     * @param requestBody
     * @param patientId
     * @returns ConditionResponse Successful Response
     * @throws ApiError
     */
    public static updateConditionApiV1ProfileConditionsConditionIdPut(
        conditionId: number,
        requestBody: ConditionUpdate,
        patientId?: (number | null),
    ): CancelablePromise<ConditionResponse> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/profile/conditions/{condition_id}',
            path: {
                'condition_id': conditionId,
            },
            query: {
                'patient_id': patientId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Condition
     * Delete a condition.
     * @param conditionId
     * @param patientId
     * @returns void
     * @throws ApiError
     */
    public static deleteConditionApiV1ProfileConditionsConditionIdDelete(
        conditionId: number,
        patientId?: (number | null),
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/profile/conditions/{condition_id}',
            path: {
                'condition_id': conditionId,
            },
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Providers
     * List healthcare providers.
     * @param patientId
     * @returns ProviderResponse Successful Response
     * @throws ApiError
     */
    public static listProvidersApiV1ProfileProvidersGet(
        patientId?: (number | null),
    ): CancelablePromise<Array<ProviderResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/profile/providers',
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Provider
     * Add a healthcare provider.
     * @param requestBody
     * @param patientId
     * @returns ProviderResponse Successful Response
     * @throws ApiError
     */
    public static createProviderApiV1ProfileProvidersPost(
        requestBody: ProviderCreate,
        patientId?: (number | null),
    ): CancelablePromise<ProviderResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/profile/providers',
            query: {
                'patient_id': patientId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Provider
     * Update a healthcare provider.
     * @param providerId
     * @param requestBody
     * @param patientId
     * @returns ProviderResponse Successful Response
     * @throws ApiError
     */
    public static updateProviderApiV1ProfileProvidersProviderIdPut(
        providerId: number,
        requestBody: ProviderUpdate,
        patientId?: (number | null),
    ): CancelablePromise<ProviderResponse> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/profile/providers/{provider_id}',
            path: {
                'provider_id': providerId,
            },
            query: {
                'patient_id': patientId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Provider
     * Delete a healthcare provider.
     * @param providerId
     * @param patientId
     * @returns void
     * @throws ApiError
     */
    public static deleteProviderApiV1ProfileProvidersProviderIdDelete(
        providerId: number,
        patientId?: (number | null),
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/profile/providers/{provider_id}',
            path: {
                'provider_id': providerId,
            },
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Lifestyle
     * Get lifestyle information.
     * @param patientId
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getLifestyleApiV1ProfileLifestyleGet(
        patientId?: (number | null),
    ): CancelablePromise<(LifestyleResponse | null)> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/profile/lifestyle',
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Lifestyle
     * Update lifestyle information.
     * @param requestBody
     * @param patientId
     * @returns LifestyleResponse Successful Response
     * @throws ApiError
     */
    public static updateLifestyleApiV1ProfileLifestylePut(
        requestBody: LifestyleUpdate,
        patientId?: (number | null),
    ): CancelablePromise<LifestyleResponse> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/profile/lifestyle',
            query: {
                'patient_id': patientId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Insurance
     * List insurance information.
     * @param patientId
     * @returns InsuranceResponse Successful Response
     * @throws ApiError
     */
    public static listInsuranceApiV1ProfileInsuranceGet(
        patientId?: (number | null),
    ): CancelablePromise<Array<InsuranceResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/profile/insurance',
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Insurance
     * Add insurance information.
     * @param requestBody
     * @param patientId
     * @returns InsuranceResponse Successful Response
     * @throws ApiError
     */
    public static createInsuranceApiV1ProfileInsurancePost(
        requestBody: InsuranceCreate,
        patientId?: (number | null),
    ): CancelablePromise<InsuranceResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/profile/insurance',
            query: {
                'patient_id': patientId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Insurance
     * Delete insurance information.
     * @param insuranceId
     * @param patientId
     * @returns void
     * @throws ApiError
     */
    public static deleteInsuranceApiV1ProfileInsuranceInsuranceIdDelete(
        insuranceId: number,
        patientId?: (number | null),
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/profile/insurance/{insurance_id}',
            path: {
                'insurance_id': insuranceId,
            },
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Family History
     * List family medical history.
     * @param patientId
     * @returns FamilyHistoryResponse Successful Response
     * @throws ApiError
     */
    public static listFamilyHistoryApiV1ProfileFamilyHistoryGet(
        patientId?: (number | null),
    ): CancelablePromise<Array<FamilyHistoryResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/profile/family-history',
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Family History
     * Add family history entry.
     * @param requestBody
     * @param patientId
     * @returns FamilyHistoryResponse Successful Response
     * @throws ApiError
     */
    public static createFamilyHistoryApiV1ProfileFamilyHistoryPost(
        requestBody: FamilyHistoryCreate,
        patientId?: (number | null),
    ): CancelablePromise<FamilyHistoryResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/profile/family-history',
            query: {
                'patient_id': patientId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Family History
     * Delete family history entry.
     * @param historyId
     * @param patientId
     * @returns void
     * @throws ApiError
     */
    public static deleteFamilyHistoryApiV1ProfileFamilyHistoryHistoryIdDelete(
        historyId: number,
        patientId?: (number | null),
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/profile/family-history/{history_id}',
            path: {
                'history_id': historyId,
            },
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Vaccinations
     * List vaccinations.
     * @param patientId
     * @returns VaccinationResponse Successful Response
     * @throws ApiError
     */
    public static listVaccinationsApiV1ProfileVaccinationsGet(
        patientId?: (number | null),
    ): CancelablePromise<Array<VaccinationResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/profile/vaccinations',
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Vaccination
     * Add a vaccination record.
     * @param requestBody
     * @param patientId
     * @returns VaccinationResponse Successful Response
     * @throws ApiError
     */
    public static createVaccinationApiV1ProfileVaccinationsPost(
        requestBody: VaccinationCreate,
        patientId?: (number | null),
    ): CancelablePromise<VaccinationResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/profile/vaccinations',
            query: {
                'patient_id': patientId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Vaccination
     * Delete a vaccination record.
     * @param vaccinationId
     * @param patientId
     * @returns void
     * @throws ApiError
     */
    public static deleteVaccinationApiV1ProfileVaccinationsVaccinationIdDelete(
        vaccinationId: number,
        patientId?: (number | null),
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/profile/vaccinations/{vaccination_id}',
            path: {
                'vaccination_id': vaccinationId,
            },
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Growth Measurements
     * List growth measurements.
     * @param patientId
     * @returns GrowthMeasurementResponse Successful Response
     * @throws ApiError
     */
    public static listGrowthMeasurementsApiV1ProfileGrowthGet(
        patientId?: (number | null),
    ): CancelablePromise<Array<GrowthMeasurementResponse>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/profile/growth',
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Growth Measurement
     * Add a growth measurement.
     * @param requestBody
     * @param patientId
     * @returns GrowthMeasurementResponse Successful Response
     * @throws ApiError
     */
    public static createGrowthMeasurementApiV1ProfileGrowthPost(
        requestBody: GrowthMeasurementCreate,
        patientId?: (number | null),
    ): CancelablePromise<GrowthMeasurementResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/profile/growth',
            query: {
                'patient_id': patientId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Growth Measurement
     * Delete a growth measurement.
     * @param measurementId
     * @param patientId
     * @returns void
     * @throws ApiError
     */
    public static deleteGrowthMeasurementApiV1ProfileGrowthMeasurementIdDelete(
        measurementId: number,
        patientId?: (number | null),
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/profile/growth/{measurement_id}',
            path: {
                'measurement_id': measurementId,
            },
            query: {
                'patient_id': patientId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
}
