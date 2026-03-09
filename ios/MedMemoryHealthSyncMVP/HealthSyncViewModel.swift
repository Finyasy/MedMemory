import Foundation
import SwiftUI

@MainActor
final class HealthSyncViewModel: ObservableObject {
    private let mobileTokenAccount = "mobile_access_token"
    private let mobileRefreshTokenAccount = "mobile_refresh_token"
    private let mobileTokenExpiresAtKey = "healthsync.mobileTokenExpiresAt"
    private let mobileTokenScopesKey = "healthsync.mobileTokenScopes"

    @Published var config = SyncConfig()
    @Published var authorizationRequested = false
    @Published var isAuthorizing = false
    @Published var isSyncing = false
    @Published var isIssuingMobileToken = false
    @Published var lastError: String?
    @Published var statusMessage: String = "Ready"
    @Published var lastResponse: AppleHealthStepsSyncResponseDTO?
    @Published var lastSamplesPreview: [DailyStepSample] = []
    @Published var lastSyncStartedAt: Date?
    @Published var isLoadingPatientData = false
    @Published var patientDataError: String?
    @Published var profileSummary: PatientProfileSummaryDTO?
    @Published var dashboardHighlights: DashboardHighlightsResponseDTO?
    @Published var recentRecords: [MedicalRecordDTO] = []
    @Published var recentDocuments: [DocumentItemDTO] = []
    @Published var appleHealthStatus: AppleHealthSyncStatusDTO?
    @Published var appleHealthTrend: AppleHealthStepsTrendResponseDTO?
    @Published var chatMessages: [PatientChatMessage] = [
        PatientChatMessage(
            role: .assistant,
            text: "Ask about a report, lab value, medication, or date. I will only use what is in the record.",
            citationCount: nil,
            isError: false
        )
    ]
    @Published var chatDraft = ""
    @Published var isSendingChat = false
    @Published var workspaceStatusMessage: String?
    @Published var workspaceError: String?
    @Published var isUploadingDocument = false
    @Published var isCreatingRecord = false
    @Published var hasStoredMobileToken = false
    @Published var mobileTokenExpiresAt: Date?
    @Published var mobileTokenScopes: [String] = []
    @Published var authProbeMessage: String?

    private let healthKit = HealthKitManager()
    private let backendClient = MedMemoryBackendClient()
    private let defaults = UserDefaults.standard
    private let keychain = KeychainTokenStore()
    private var hasLoadedPatientData = false
    private var lastConversationID: String?

    init() {
        loadSavedConfig()
        loadStoredMobileTokenState()
    }

    func requestHealthAccess() async {
        isAuthorizing = true
        lastError = nil
        defer { isAuthorizing = false }

        do {
            try await healthKit.requestStepReadAuthorization()
            authorizationRequested = true
            statusMessage = "HealthKit access granted for step count."
        } catch {
            lastError = error.localizedDescription
            statusMessage = "HealthKit access failed."
        }
    }

    func syncNow() async {
        isSyncing = true
        lastError = nil
        lastResponse = nil
        lastSyncStartedAt = Date()
        statusMessage = "Reading steps from Apple Health…"
        persistConfig()
        defer { isSyncing = false }

        do {
            let samples = try await healthKit.fetchDailySteps(lastNDays: config.daysBack)
            lastSamplesPreview = Array(samples.suffix(7))
            statusMessage = "Uploading \(samples.count) daily totals to MedMemory…"
            let response = try await runWithAutoRefresh {
                try await backendClient.syncDailySteps(
                    config: self.config,
                    samples: samples,
                    accessTokenOverride: self.effectiveAccessToken
                )
            }
            lastResponse = response
            statusMessage = "Sync complete: \(response.inserted_days) inserted, \(response.updated_days) updated."
            await loadPatientExperience(force: true)
        } catch {
            lastError = error.localizedDescription
            statusMessage = "Sync failed."
        }
    }

    func retryLastSync() async {
        await syncNow()
    }

    var accessTokenSourceDescription: String {
        let enteredToken = sanitizedToken(config.bearerToken)
        if !enteredToken.isEmpty {
            return "Using token entered in this screen"
        }
        if hasStoredMobileToken {
            return "Using mobile token stored in Keychain"
        }
        return "No access token configured"
    }

    var accessTokenFingerprint: String {
        guard let token = effectiveAccessToken, !token.isEmpty else {
            return "none"
        }
        return String(token.suffix(12))
    }

    func probeAuth() async {
        lastError = nil
        authProbeMessage = nil
        persistConfig()

        do {
            let profile = try await runWithAutoRefresh {
                try await backendClient.probeProfileAccess(
                    config: self.effectiveConfig,
                    accessTokenOverride: self.effectiveAccessToken
                )
            }
            authProbeMessage = "Auth OK for patient \(profile.id) using token suffix \(accessTokenFingerprint)"
        } catch {
            authProbeMessage = error.localizedDescription
            lastError = error.localizedDescription
        }
    }

    func issueMobileToken() async {
        isIssuingMobileToken = true
        lastError = nil
        statusMessage = "Issuing mobile token…"
        persistConfig()
        defer { isIssuingMobileToken = false }

        let bootstrapToken = sanitizedToken(config.bearerToken)
        guard !bootstrapToken.isEmpty else {
            lastError = "Paste a patient web token once to issue a mobile token."
            statusMessage = "Mobile token not issued."
            return
        }

        do {
            let response = try await backendClient.issueMobileToken(
                config: config,
                bootstrapToken: bootstrapToken,
                scopes: ["chat", "records", "documents", "apple_health"]
            )
            try persistMobileSession(response)
            statusMessage = "Mobile token stored securely in Keychain."
            await loadPatientExperience(force: true)
        } catch {
            lastError = error.localizedDescription
            statusMessage = "Mobile token request failed."
        }
    }

    func clearMobileToken() {
        do {
            try keychain.deleteToken(account: mobileTokenAccount)
            try keychain.deleteToken(account: mobileRefreshTokenAccount)
        } catch {
            lastError = error.localizedDescription
        }
        config.bearerToken = ""
        authProbeMessage = nil
        hasStoredMobileToken = false
        mobileTokenExpiresAt = nil
        mobileTokenScopes = []
        defaults.removeObject(forKey: mobileTokenExpiresAtKey)
        defaults.removeObject(forKey: mobileTokenScopesKey)
    }

    func loadPatientExperience(force: Bool = false) async {
        if isLoadingPatientData { return }
        if hasLoadedPatientData && !force { return }

        isLoadingPatientData = true
        patientDataError = nil
        persistConfig()
        defer { isLoadingPatientData = false }

        do {
            let snapshot = try await runWithAutoRefresh {
                try await backendClient.fetchPatientExperienceSnapshot(
                    config: self.effectiveConfig
                )
            }
            profileSummary = snapshot.profile
            dashboardHighlights = snapshot.highlights
            recentRecords = snapshot.records
            recentDocuments = snapshot.documents
            appleHealthStatus = snapshot.appleHealthStatus
            appleHealthTrend = snapshot.appleHealthTrend
            hasLoadedPatientData = true
        } catch {
            patientDataError = error.localizedDescription
        }
    }

    func sendChatMessage() async {
        let trimmed = chatDraft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        guard effectiveConfig.patientID != nil else {
            lastError = "Enter a patient ID before sending chat requests."
            return
        }

        isSendingChat = true
        lastError = nil
        chatMessages.append(
            PatientChatMessage(role: .user, text: trimmed, citationCount: nil, isError: false)
        )
        chatDraft = ""
        defer { isSendingChat = false }

        do {
            let response = try await runWithAutoRefresh {
                try await backendClient.askChatQuestion(
                    config: self.effectiveConfig,
                    accessTokenOverride: self.effectiveAccessToken,
                    question: trimmed,
                    conversationID: self.lastConversationID
                )
            }
            lastConversationID = response.conversation_id
            chatMessages.append(
                PatientChatMessage(
                    role: .assistant,
                    text: response.answer,
                    citationCount: response.num_sources,
                    isError: false
                )
            )
        } catch {
            chatMessages.append(
                PatientChatMessage(
                    role: .assistant,
                    text: error.localizedDescription,
                    citationCount: nil,
                    isError: true
                )
            )
            lastError = error.localizedDescription
        }
    }

    func createRecord(title: String, content: String, recordType: String) async {
        isCreatingRecord = true
        workspaceError = nil
        workspaceStatusMessage = nil
        defer { isCreatingRecord = false }

        do {
            let record = try await runWithAutoRefresh {
                try await backendClient.createRecord(
                    config: self.effectiveConfig,
                    accessTokenOverride: self.effectiveAccessToken,
                    title: title,
                    content: content,
                    recordType: recordType
                )
            }
            recentRecords.insert(record, at: 0)
            workspaceStatusMessage = "Saved record: \(record.title)"
            hasLoadedPatientData = false
            await loadPatientExperience(force: true)
        } catch {
            workspaceError = error.localizedDescription
        }
    }

    func uploadDocument(fileURL: URL) async {
        isUploadingDocument = true
        workspaceError = nil
        workspaceStatusMessage = nil
        defer { isUploadingDocument = false }

        let startedAccess = fileURL.startAccessingSecurityScopedResource()
        defer {
            if startedAccess {
                fileURL.stopAccessingSecurityScopedResource()
            }
        }

        do {
            let document = try await runWithAutoRefresh {
                try await backendClient.uploadDocument(
                    config: self.effectiveConfig,
                    accessTokenOverride: self.effectiveAccessToken,
                    fileURL: fileURL,
                    title: fileURL.deletingPathExtension().lastPathComponent
                )
            }
            recentDocuments.insert(document, at: 0)
            workspaceStatusMessage = "Uploaded document: \(document.title ?? document.original_filename)"
            hasLoadedPatientData = false
            await loadPatientExperience(force: true)
        } catch {
            workspaceError = error.localizedDescription
        }
    }

    private var effectiveAccessToken: String? {
        let enteredToken = sanitizedToken(config.bearerToken)
        if !enteredToken.isEmpty {
            return enteredToken
        }
        do {
            return sanitizedToken((try keychain.readToken(account: mobileTokenAccount)) ?? "")
        } catch {
            return nil
        }
    }

    private var effectiveConfig: SyncConfig {
        var resolved = config
        resolved.bearerToken = effectiveAccessToken ?? config.bearerToken
        return resolved
    }

    private func runWithAutoRefresh<T>(
        _ operation: () async throws -> T
    ) async throws -> T {
        do {
            return try await operation()
        } catch let error as HealthSyncError {
            if case .httpError(401, _) = error,
               try await refreshMobileSessionIfPossible() {
                return try await operation()
            }
            throw error
        }
    }

    private func persistConfig() {
        defaults.set(config.baseURL, forKey: "healthsync.baseURL")
        defaults.set(config.patientIDText, forKey: "healthsync.patientIDText")
        defaults.set(config.daysBack, forKey: "healthsync.daysBack")
    }

    private func loadSavedConfig() {
        if let baseURL = defaults.string(forKey: "healthsync.baseURL"), !baseURL.isEmpty {
            config.baseURL = baseURL
        }
        if let patientIDText = defaults.string(forKey: "healthsync.patientIDText"), !patientIDText.isEmpty {
            config.patientIDText = patientIDText
        }
        defaults.removeObject(forKey: "healthsync.bearerToken")
        let daysBack = defaults.integer(forKey: "healthsync.daysBack")
        if daysBack > 0 {
            config.daysBack = min(max(daysBack, 1), 365)
        }
    }

    private func loadStoredMobileTokenState() {
        do {
            hasStoredMobileToken = !sanitizedToken((try keychain.readToken(account: mobileTokenAccount)) ?? "").isEmpty
        } catch {
            hasStoredMobileToken = false
        }
        let expiresAt = defaults.double(forKey: mobileTokenExpiresAtKey)
        if expiresAt > 0 {
            mobileTokenExpiresAt = Date(timeIntervalSince1970: expiresAt)
        }
        mobileTokenScopes = defaults.stringArray(forKey: mobileTokenScopesKey) ?? []
    }

    private func refreshMobileSessionIfPossible() async throws -> Bool {
        let refreshToken = sanitizedToken((try keychain.readToken(account: mobileRefreshTokenAccount)) ?? "")
        guard !refreshToken.isEmpty else {
            return false
        }
        let response = try await backendClient.refreshMobileToken(
            config: config,
            refreshToken: refreshToken
        )
        try persistMobileSession(response)
        statusMessage = "Mobile session refreshed. Retrying…"
        return true
    }

    private func persistMobileSession(_ response: MobileTokenResponseDTO) throws {
        try keychain.saveToken(response.access_token, account: mobileTokenAccount)
        try keychain.saveToken(response.refresh_token, account: mobileRefreshTokenAccount)
        config.bearerToken = response.access_token
        hasStoredMobileToken = true
        mobileTokenScopes = response.scopes
        mobileTokenExpiresAt = Date().addingTimeInterval(TimeInterval(response.expires_in))
        defaults.set(mobileTokenExpiresAt?.timeIntervalSince1970, forKey: mobileTokenExpiresAtKey)
        defaults.set(response.scopes, forKey: mobileTokenScopesKey)
    }

    private func sanitizedToken(_ rawValue: String) -> String {
        var token = rawValue.filter { !$0.isWhitespace && !$0.isNewline }
        if token.hasPrefix("\""), token.hasSuffix("\""), token.count >= 2 {
            token.removeFirst()
            token.removeLast()
        }
        return token
    }
}
