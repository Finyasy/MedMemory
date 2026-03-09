import Foundation

struct DailyStepSample: Identifiable, Hashable {
    let id = UUID()
    let sampleDate: Date
    let stepCount: Int
    let startAt: Date
    let endAt: Date
    let timeZoneIdentifier: String
    let sourceName: String
    let sourceBundleId: String?
    let sourceUUID: String?
}

struct SyncConfig {
    var baseURL: String = "http://192.168.1.25:8000"
    var patientIDText: String = ""
    var bearerToken: String = ""
    var daysBack: Int = 14

    var patientID: Int? {
        Int(patientIDText.trimmingCharacters(in: .whitespacesAndNewlines))
    }

    var normalizedAPIBaseURL: URL? {
        let trimmed = baseURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, var components = URLComponents(string: trimmed) else {
            return nil
        }
        var path = components.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        if path.hasSuffix("api/v1") {
            // already normalized
        } else if path.hasSuffix("api") {
            path = path + "/v1"
        } else if path.isEmpty {
            path = "api/v1"
        } else {
            path = path + "/api/v1"
        }
        components.path = "/" + path
        return components.url
    }
}

struct MobileTokenRequestPayload: Encodable {
    let patient_id: Int
    let scopes: [String]
}

struct MobileTokenResponseDTO: Decodable {
    let access_token: String
    let refresh_token: String
    let token_type: String
    let expires_in: Int
    let patient_id: Int
    let scopes: [String]
}

struct RefreshTokenRequestPayload: Encodable {
    let refresh_token: String
}

struct AppleHealthStepSamplePayload: Encodable {
    let sample_date: String
    let step_count: Int
    let start_at: String
    let end_at: String
    let timezone: String
    let source_name: String
    let source_bundle_id: String?
    let source_uuid: String?
}

struct AppleHealthStepsSyncRequestPayload: Encodable {
    let samples: [AppleHealthStepSamplePayload]
    let client_anchor: String?
    let sync_started_at: String
    let sync_completed_at: String
    let device_name: String?
    let app_version: String?
}

struct AppleHealthStepsSyncResponseDTO: Decodable {
    let patient_id: Int
    let provider_slug: String
    let received_samples: Int
    let unique_days_received: Int
    let inserted_days: Int
    let updated_days: Int
    let unchanged_days: Int
    let latest_sample_date: String?
    let last_synced_at: String?
    let connection_status: String
    let client_anchor: String?
}

struct PatientProfileSummaryDTO: Decodable {
    let id: Int
    let full_name: String
    let age: Int?
    let date_of_birth: String?
}

struct DashboardSummaryDTO: Decodable {
    let out_of_range: Int
    let in_range: Int
    let tracked_metrics: Int
    let last_updated_at: String?
}

struct HighlightItemDTO: Decodable, Identifiable {
    let metric_key: String
    let metric_name: String
    let value: String?
    let numeric_value: Double?
    let unit: String?
    let observed_at: String?
    let status: String
    let direction: String?

    var id: String { metric_key }
}

struct DashboardHighlightsResponseDTO: Decodable {
    let patient_id: Int
    let summary: DashboardSummaryDTO
    let highlights: [HighlightItemDTO]
}

struct MedicalRecordDTO: Decodable, Identifiable {
    let id: Int
    let patient_id: Int
    let title: String
    let content: String
    let record_type: String?
    let created_at: String?
}

struct DocumentItemDTO: Decodable, Identifiable {
    let id: Int
    let patient_id: Int
    let document_type: String
    let title: String?
    let original_filename: String
    let description: String?
    let processing_status: String
    let is_processed: Bool
    let page_count: Int?
}

struct ChatSourceDTO: Decodable {
    let source_type: String
    let source_id: Int?
    let relevance: Double
}

struct ChatResponseDTO: Decodable {
    let answer: String
    let conversation_id: String?
    let num_sources: Int?
    let sources: [ChatSourceDTO]?
}

struct RecordCreatePayload: Encodable {
    let title: String
    let content: String
    let record_type: String
}

struct AppleHealthStepTrendPointDTO: Decodable, Identifiable {
    let sample_date: String
    let step_count: Int
    let start_at: String?
    let end_at: String?
    let timezone: String?
    let source_name: String?

    var id: String { sample_date }
}

struct AppleHealthStepsTrendResponseDTO: Decodable {
    let patient_id: Int
    let metric_key: String
    let metric_name: String
    let unit: String
    let start_date: String
    let end_date: String
    let points: [AppleHealthStepTrendPointDTO]
    let total_steps: Int
    let average_steps: Double?
    let latest_step_count: Int?
    let latest_sample_date: String?
    let last_synced_at: String?
}

struct AppleHealthSyncStatusDTO: Decodable {
    let patient_id: Int
    let provider_name: String
    let provider_slug: String
    let status: String
    let is_active: Bool
    let last_synced_at: String?
    let last_error: String?
    let total_synced_days: Int
    let earliest_sample_date: String?
    let latest_sample_date: String?
}

struct PatientExperienceSnapshotDTO {
    let profile: PatientProfileSummaryDTO
    let highlights: DashboardHighlightsResponseDTO
    let records: [MedicalRecordDTO]
    let documents: [DocumentItemDTO]
    let appleHealthStatus: AppleHealthSyncStatusDTO
    let appleHealthTrend: AppleHealthStepsTrendResponseDTO
}

enum HealthSyncError: LocalizedError {
    case invalidConfig(String)
    case healthDataUnavailable
    case httpError(Int, String)
    case decodingError(String)

    var errorDescription: String? {
        switch self {
        case .invalidConfig(let message):
            return message
        case .healthDataUnavailable:
            return "HealthKit is not available on this device."
        case .httpError(let code, let message):
            if code == 401 {
                return "Backend request failed (401): token rejected. Clear the stored mobile token, paste a fresh token, or issue a new mobile token. Server said: \(message)"
            }
            return "Backend request failed (\(code)): \(message)"
        case .decodingError(let message):
            return "Failed to decode backend response: \(message)"
        }
    }
}
