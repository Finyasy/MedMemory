import Foundation
import UIKit

final class MedMemoryBackendClient {
    private let session: URLSession
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder
    private let isoFormatter: ISO8601DateFormatter

    init(session: URLSession = .shared) {
        self.session = session
        self.encoder = JSONEncoder()
        self.decoder = JSONDecoder()
        self.isoFormatter = ISO8601DateFormatter()
        self.isoFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    }

    func fetchPatientExperienceSnapshot(config: SyncConfig) async throws -> PatientExperienceSnapshotDTO {
        guard let patientID = config.patientID else {
            throw HealthSyncError.invalidConfig("Enter a valid patient ID.")
        }

        async let profile = fetch(
            config: config,
            pathComponents: ["profile"],
            queryItems: [URLQueryItem(name: "patient_id", value: String(patientID))]
        ) as PatientProfileSummaryDTO

        async let highlights = fetch(
            config: config,
            pathComponents: ["dashboard", "patient", String(patientID), "highlights"],
            queryItems: [URLQueryItem(name: "limit", value: "5")]
        ) as DashboardHighlightsResponseDTO

        async let records = fetch(
            config: config,
            pathComponents: ["records"],
            queryItems: [URLQueryItem(name: "patient_id", value: String(patientID))]
        ) as [MedicalRecordDTO]

        async let documents = fetch(
            config: config,
            pathComponents: ["documents"],
            queryItems: [URLQueryItem(name: "patient_id", value: String(patientID))]
        ) as [DocumentItemDTO]

        async let appleHealthStatus = fetch(
            config: config,
            pathComponents: ["integrations", "apple-health", "patient", String(patientID), "status"]
        ) as AppleHealthSyncStatusDTO

        async let appleHealthTrend = fetch(
            config: config,
            pathComponents: ["integrations", "apple-health", "patient", String(patientID), "steps"],
            queryItems: [URLQueryItem(name: "days", value: "14")]
        ) as AppleHealthStepsTrendResponseDTO

        return try await PatientExperienceSnapshotDTO(
            profile: profile,
            highlights: highlights,
            records: records,
            documents: documents,
            appleHealthStatus: appleHealthStatus,
            appleHealthTrend: appleHealthTrend
        )
    }

    func syncDailySteps(
        config: SyncConfig,
        samples: [DailyStepSample],
        clientAnchor: String? = nil
    ) async throws -> AppleHealthStepsSyncResponseDTO {
        guard let patientID = config.patientID else {
            throw HealthSyncError.invalidConfig("Enter a valid patient ID.")
        }

        let syncStartedAt = Date()
        let payload = AppleHealthStepsSyncRequestPayload(
            samples: samples.map { sample in
                AppleHealthStepSamplePayload(
                    sample_date: self.dateOnlyString(sample.sampleDate),
                    step_count: sample.stepCount,
                    start_at: self.isoString(sample.startAt),
                    end_at: self.isoString(sample.endAt),
                    timezone: sample.timeZoneIdentifier,
                    source_name: sample.sourceName,
                    source_bundle_id: sample.sourceBundleId,
                    source_uuid: sample.sourceUUID
                )
            },
            client_anchor: clientAnchor,
            sync_started_at: isoString(syncStartedAt),
            sync_completed_at: isoString(Date()),
            device_name: UIDevice.current.name,
            app_version: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String
        )
        let apiRequest = try authorizedRequest(
            config: config,
            pathComponents: [
                "integrations",
                "apple-health",
                "patient",
                String(patientID),
                "steps",
                "sync",
            ],
            method: "POST",
            body: try encoder.encode(payload)
        )
        return try await perform(apiRequest)
    }

    private func isoString(_ date: Date) -> String {
        isoFormatter.string(from: date)
    }

    private func dateOnlyString(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: date)
    }

    private func fetch<T: Decodable>(
        config: SyncConfig,
        pathComponents: [String],
        queryItems: [URLQueryItem] = []
    ) async throws -> T {
        let request = try authorizedRequest(
            config: config,
            pathComponents: pathComponents,
            queryItems: queryItems
        )
        return try await perform(request)
    }

    private func perform<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw HealthSyncError.invalidConfig("Invalid backend response.")
        }
        guard (200...299).contains(http.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw HealthSyncError.httpError(http.statusCode, message)
        }
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw HealthSyncError.decodingError(error.localizedDescription)
        }
    }

    private func authorizedRequest(
        config: SyncConfig,
        pathComponents: [String],
        queryItems: [URLQueryItem] = [],
        method: String = "GET",
        body: Data? = nil
    ) throws -> URLRequest {
        guard let apiBase = config.normalizedAPIBaseURL else {
            throw HealthSyncError.invalidConfig("Enter a valid backend URL.")
        }
        let token = config.bearerToken.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !token.isEmpty else {
            throw HealthSyncError.invalidConfig("Paste a MedMemory bearer token.")
        }

        var components = URLComponents(url: apiBase, resolvingAgainstBaseURL: false)
        var path = components?.path.trimmingCharacters(in: CharacterSet(charactersIn: "/")) ?? ""
        let suffix = pathComponents.joined(separator: "/")
        if path.isEmpty {
            path = suffix
        } else {
            path = path + "/" + suffix
        }
        components?.path = "/" + path
        if !queryItems.isEmpty {
            components?.queryItems = queryItems
        }
        guard let url = components?.url else {
            throw HealthSyncError.invalidConfig("Unable to build backend URL.")
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        if body != nil {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = body
        }
        return request
    }
}
