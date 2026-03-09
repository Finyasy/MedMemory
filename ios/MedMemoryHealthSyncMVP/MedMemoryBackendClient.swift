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
            accessTokenOverride: nil,
            pathComponents: ["profile"],
            queryItems: [URLQueryItem(name: "patient_id", value: String(patientID))]
        ) as PatientProfileSummaryDTO

        async let highlights = fetch(
            config: config,
            accessTokenOverride: nil,
            pathComponents: ["dashboard", "patient", String(patientID), "highlights"],
            queryItems: [URLQueryItem(name: "limit", value: "5")]
        ) as DashboardHighlightsResponseDTO

        async let records = fetch(
            config: config,
            accessTokenOverride: nil,
            pathComponents: ["records"],
            queryItems: [URLQueryItem(name: "patient_id", value: String(patientID))]
        ) as [MedicalRecordDTO]

        async let documents = fetch(
            config: config,
            accessTokenOverride: nil,
            pathComponents: ["documents"],
            queryItems: [URLQueryItem(name: "patient_id", value: String(patientID))]
        ) as [DocumentItemDTO]

        async let appleHealthStatus = fetch(
            config: config,
            accessTokenOverride: nil,
            pathComponents: ["integrations", "apple-health", "patient", String(patientID), "status"]
        ) as AppleHealthSyncStatusDTO

        async let appleHealthTrend = fetch(
            config: config,
            accessTokenOverride: nil,
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

    func probeProfileAccess(
        config: SyncConfig,
        accessTokenOverride: String? = nil
    ) async throws -> PatientProfileSummaryDTO {
        guard let patientID = config.patientID else {
            throw HealthSyncError.invalidConfig("Enter a valid patient ID.")
        }
        return try await fetch(
            config: config,
            accessTokenOverride: accessTokenOverride,
            pathComponents: ["profile"],
            queryItems: [URLQueryItem(name: "patient_id", value: String(patientID))]
        )
    }

    func syncDailySteps(
        config: SyncConfig,
        samples: [DailyStepSample],
        accessTokenOverride: String? = nil,
        clientAnchor: String? = nil
    ) async throws -> AppleHealthStepsSyncResponseDTO {
        guard let patientID = config.patientID else {
            throw HealthSyncError.invalidConfig("Enter a valid patient ID.")
        }

        let syncStartedAt = Date()
        let deviceName = await MainActor.run { UIDevice.current.name }
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
            device_name: deviceName,
            app_version: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String
        )
        let apiRequest = try authorizedRequest(
            config: config,
            accessTokenOverride: accessTokenOverride,
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

    func issueMobileToken(
        config: SyncConfig,
        bootstrapToken: String,
        scopes: [String]
    ) async throws -> MobileTokenResponseDTO {
        guard let patientID = config.patientID else {
            throw HealthSyncError.invalidConfig("Enter a valid patient ID.")
        }
        let payload = MobileTokenRequestPayload(patient_id: patientID, scopes: scopes)
        let request = try authorizedRequest(
            config: config,
            accessTokenOverride: bootstrapToken,
            pathComponents: ["auth", "mobile-token"],
            method: "POST",
            body: try encoder.encode(payload)
        )
        return try await perform(request)
    }

    func refreshMobileToken(
        config: SyncConfig,
        refreshToken: String
    ) async throws -> MobileTokenResponseDTO {
        let payload = RefreshTokenRequestPayload(refresh_token: refreshToken)
        let request = try authorizedRequest(
            config: config,
            accessTokenOverride: refreshToken,
            pathComponents: ["auth", "mobile-refresh"],
            method: "POST",
            body: try encoder.encode(payload)
        )
        return try await perform(request)
    }

    func askChatQuestion(
        config: SyncConfig,
        accessTokenOverride: String? = nil,
        question: String,
        conversationID: String? = nil
    ) async throws -> ChatResponseDTO {
        guard let patientID = config.patientID else {
            throw HealthSyncError.invalidConfig("Enter a valid patient ID.")
        }
        struct Payload: Encodable {
            let question: String
            let patient_id: Int
            let conversation_id: String?
        }
        let payload = Payload(
            question: question,
            patient_id: patientID,
            conversation_id: conversationID
        )
        let request = try authorizedRequest(
            config: config,
            accessTokenOverride: accessTokenOverride,
            pathComponents: ["chat", "ask"],
            method: "POST",
            body: try encoder.encode(payload)
        )
        return try await perform(request)
    }

    func createRecord(
        config: SyncConfig,
        accessTokenOverride: String? = nil,
        title: String,
        content: String,
        recordType: String
    ) async throws -> MedicalRecordDTO {
        guard let patientID = config.patientID else {
            throw HealthSyncError.invalidConfig("Enter a valid patient ID.")
        }
        let payload = RecordCreatePayload(
            title: title,
            content: content,
            record_type: recordType
        )
        let request = try authorizedRequest(
            config: config,
            accessTokenOverride: accessTokenOverride,
            pathComponents: ["records"],
            queryItems: [URLQueryItem(name: "patient_id", value: String(patientID))],
            method: "POST",
            body: try encoder.encode(payload)
        )
        return try await perform(request)
    }

    func uploadDocument(
        config: SyncConfig,
        accessTokenOverride: String? = nil,
        fileURL: URL,
        documentType: String = "general",
        title: String? = nil,
        description: String? = nil
    ) async throws -> DocumentItemDTO {
        guard let patientID = config.patientID else {
            throw HealthSyncError.invalidConfig("Enter a valid patient ID.")
        }
        guard let apiBase = config.normalizedAPIBaseURL else {
            throw HealthSyncError.invalidConfig("Enter a valid backend URL.")
        }
        let token = try resolveAccessToken(config: config, accessTokenOverride: accessTokenOverride)
        let boundary = "Boundary-\(UUID().uuidString)"
        var request = URLRequest(
            url: apiBase
                .appendingPathComponent("documents")
                .appendingPathComponent("upload")
        )
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        let fileData = try Data(contentsOf: fileURL)
        let filename = fileURL.lastPathComponent
        let mimeType = mimeType(for: fileURL)

        var body = Data()
        appendFormField("patient_id", value: String(patientID), to: &body, boundary: boundary)
        appendFormField("document_type", value: documentType, to: &body, boundary: boundary)
        if let title, !title.isEmpty {
            appendFormField("title", value: title, to: &body, boundary: boundary)
        }
        if let description, !description.isEmpty {
            appendFormField("description", value: description, to: &body, boundary: boundary)
        }
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append(
            "Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n".data(using: .utf8)!
        )
        body.append("Content-Type: \(mimeType)\r\n\r\n".data(using: .utf8)!)
        body.append(fileData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)

        request.httpBody = body
        return try await perform(request)
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
        accessTokenOverride: String?,
        pathComponents: [String],
        queryItems: [URLQueryItem] = []
    ) async throws -> T {
        let request = try authorizedRequest(
            config: config,
            accessTokenOverride: accessTokenOverride,
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
        accessTokenOverride: String? = nil,
        pathComponents: [String],
        queryItems: [URLQueryItem] = [],
        method: String = "GET",
        body: Data? = nil
    ) throws -> URLRequest {
        guard let apiBase = config.normalizedAPIBaseURL else {
            throw HealthSyncError.invalidConfig("Enter a valid backend URL.")
        }
        let token = try resolveAccessToken(config: config, accessTokenOverride: accessTokenOverride)

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

    private func resolveAccessToken(
        config: SyncConfig,
        accessTokenOverride: String?
    ) throws -> String {
        let token = (accessTokenOverride ?? config.bearerToken)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !token.isEmpty else {
            throw HealthSyncError.invalidConfig("Issue or paste a valid MedMemory token.")
        }
        return token
    }

    private func appendFormField(
        _ name: String,
        value: String,
        to body: inout Data,
        boundary: String
    ) {
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n".data(using: .utf8)!)
        body.append("\(value)\r\n".data(using: .utf8)!)
    }

    private func mimeType(for url: URL) -> String {
        switch url.pathExtension.lowercased() {
        case "pdf":
            return "application/pdf"
        case "png":
            return "image/png"
        case "jpg", "jpeg":
            return "image/jpeg"
        default:
            return "application/octet-stream"
        }
    }
}
