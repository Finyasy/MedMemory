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

    func syncDailySteps(
        config: SyncConfig,
        samples: [DailyStepSample],
        clientAnchor: String? = nil
    ) async throws -> AppleHealthStepsSyncResponseDTO {
        guard let patientID = config.patientID else {
            throw HealthSyncError.invalidConfig("Enter a valid patient ID.")
        }
        guard let apiBase = config.normalizedAPIBaseURL else {
            throw HealthSyncError.invalidConfig("Enter a valid backend URL.")
        }
        let token = config.bearerToken.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !token.isEmpty else {
            throw HealthSyncError.invalidConfig("Paste a MedMemory bearer token.")
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

        let endpoint = apiBase
            .appendingPathComponent("integrations")
            .appendingPathComponent("apple-health")
            .appendingPathComponent("patient")
            .appendingPathComponent(String(patientID))
            .appendingPathComponent("steps")
            .appendingPathComponent("sync")

        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.httpBody = try encoder.encode(payload)

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw HealthSyncError.invalidConfig("Invalid backend response.")
        }
        guard (200...299).contains(http.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw HealthSyncError.httpError(http.statusCode, message)
        }
        do {
            return try decoder.decode(AppleHealthStepsSyncResponseDTO.self, from: data)
        } catch {
            throw HealthSyncError.decodingError(error.localizedDescription)
        }
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
}

