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
            return "Backend request failed (\(code)): \(message)"
        case .decodingError(let message):
            return "Failed to decode backend response: \(message)"
        }
    }
}

