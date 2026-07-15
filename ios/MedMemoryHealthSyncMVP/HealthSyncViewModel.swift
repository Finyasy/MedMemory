import Foundation
import SwiftUI

@MainActor
final class HealthSyncViewModel: ObservableObject {
    private let webTokenAccount = "web_access_token"
    private let webRefreshTokenAccount = "web_refresh_token"
    private let mobileTokenAccount = "mobile_access_token"
    private let mobileRefreshTokenAccount = "mobile_refresh_token"
    private let mobileTokenExpiresAtKey = "healthsync.mobileTokenExpiresAt"
    private let mobileTokenScopesKey = "healthsync.mobileTokenScopes"

    @Published var config = SyncConfig()
    @Published var authorizationRequested = false
    @Published var isAuthorizing = false
    @Published var isSyncing = false
    @Published var isIssuingMobileToken = false
    @Published var isSigningIn = false
    @Published var isAuthenticated = false
    @Published var currentUser: CurrentUserDTO?
    @Published var authError: String?
    @Published var lastError: String?
    @Published var statusMessage: String = "Ready"
    @Published var lastResponse: AppleHealthStepsSyncResponseDTO?
    @Published var lastSamplesPreview: [DailyStepSample] = []
    @Published var lastSyncStartedAt: Date?
    @Published var isLoadingPatientData = false
    @Published var patientDataError: String?
    @Published var profileSummary: PatientProfileSummaryDTO?
    @Published var fullProfile: FullPatientProfileDTO?
    @Published var isLoadingFullProfile = false
    @Published var profileError: String?
    @Published var profileStatusMessage: String?
    @Published var isSavingProfile = false
    @Published var isMutatingProfileCollection = false
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
        loadStoredAuthState()
        loadStoredMobileTokenState()
    }

    var preferredChatLanguage: String {
        let raw = fullProfile?.preferred_language?.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard raw == "sw" || raw == "sheng" else { return "en" }
        return raw ?? "en"
    }

    var suggestedChatPrompts: [String] {
        var prompts: [String] = []
        if let allergy = fullProfile?.allergies.first {
            prompts.append("What should I know about my \(allergy.allergen) allergy?")
        }
        if let condition = fullProfile?.conditions.first(where: { $0.status == "active" }) ?? fullProfile?.conditions.first {
            prompts.append("Summarize what is in my record about \(condition.condition_name).")
        }
        if let highlight = dashboardHighlights?.highlights.first {
            prompts.append("Explain my latest \(highlight.metric_name) result.")
        }
        if let document = recentDocuments.first {
            prompts.append("Summarize \(document.title ?? document.original_filename).")
        }
        if prompts.isEmpty {
            prompts = [
                "What records are available for me?",
                "Are any recent results out of range?",
                "What should I ask my clinician next?"
            ]
        }
        return Array(prompts.prefix(4))
    }

    func useSuggestedPrompt(_ prompt: String) {
        chatDraft = prompt
    }

    func bootstrapAuthenticatedSession() async {
        guard isAuthenticated else { return }
        do {
            currentUser = try await backendClient.fetchCurrentUser(
                config: effectiveConfig,
                accessTokenOverride: effectiveAccessToken
            )
            try await selectFirstPatientIfNeeded()
            await loadPatientExperience(force: true)
        } catch {
            authError = error.localizedDescription
        }
    }

    func signIn(email: String, password: String) async {
        let trimmedEmail = email.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedEmail.isEmpty, !password.isEmpty else {
            authError = "Enter your email and password."
            return
        }

        isSigningIn = true
        authError = nil
        lastError = nil
        statusMessage = "Signing in…"
        persistConfig()
        defer { isSigningIn = false }

        do {
            let token = try await backendClient.login(
                config: config,
                email: trimmedEmail,
                password: password
            )
            try persistWebSession(token)
            currentUser = try await backendClient.fetchCurrentUser(
                config: effectiveConfig,
                accessTokenOverride: token.access_token
            )
            try await selectFirstPatientIfNeeded(accessToken: token.access_token)
            statusMessage = "Signed in as \(token.email)."
            hasLoadedPatientData = false
            await loadPatientExperience(force: true)
        } catch {
            authError = error.localizedDescription
            statusMessage = "Sign in failed."
        }
    }

    func signOut() {
        do {
            try keychain.deleteToken(account: webTokenAccount)
            try keychain.deleteToken(account: webRefreshTokenAccount)
            try keychain.deleteToken(account: mobileTokenAccount)
            try keychain.deleteToken(account: mobileRefreshTokenAccount)
        } catch {
            lastError = error.localizedDescription
        }
        config.bearerToken = ""
        config.patientIDText = ""
        currentUser = nil
        isAuthenticated = false
        hasStoredMobileToken = false
        mobileTokenExpiresAt = nil
        mobileTokenScopes = []
        authProbeMessage = nil
        authError = nil
        profileSummary = nil
        fullProfile = nil
        dashboardHighlights = nil
        recentRecords = []
        recentDocuments = []
        appleHealthStatus = nil
        appleHealthTrend = nil
        hasLoadedPatientData = false
        defaults.removeObject(forKey: mobileTokenExpiresAtKey)
        defaults.removeObject(forKey: mobileTokenScopesKey)
        persistConfig()
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
            await loadFullProfile(force: true)
        } catch {
            patientDataError = error.localizedDescription
        }
    }

    func loadFullProfile(force: Bool = false) async {
        if isLoadingFullProfile { return }
        if fullProfile != nil && !force { return }

        isLoadingFullProfile = true
        profileError = nil
        persistConfig()
        defer { isLoadingFullProfile = false }

        do {
            fullProfile = try await runWithAutoRefresh {
                try await backendClient.fetchFullProfile(
                    config: self.effectiveConfig,
                    accessTokenOverride: self.effectiveAccessToken
                )
            }
        } catch {
            profileError = error.localizedDescription
        }
    }

    func saveBasicProfile(
        firstName: String,
        lastName: String,
        dateOfBirth: String,
        sex: String,
        bloodType: String,
        heightCM: String,
        weightKG: String,
        phone: String,
        email: String,
        address: String,
        preferredLanguage: String
    ) async {
        isSavingProfile = true
        profileError = nil
        profileStatusMessage = nil
        defer { isSavingProfile = false }

        let payload = BasicProfileUpdatePayload(
            first_name: nilIfBlank(firstName),
            last_name: nilIfBlank(lastName),
            date_of_birth: nilIfBlank(dateOfBirth),
            sex: nilIfBlank(sex),
            blood_type: nilIfBlank(bloodType),
            height_cm: Double(heightCM.trimmingCharacters(in: .whitespacesAndNewlines)),
            weight_kg: Double(weightKG.trimmingCharacters(in: .whitespacesAndNewlines)),
            phone: nilIfBlank(phone),
            email: nilIfBlank(email),
            address: nilIfBlank(address),
            preferred_language: nilIfBlank(preferredLanguage),
            timezone: TimeZone.current.identifier
        )

        do {
            fullProfile = try await runWithAutoRefresh {
                try await backendClient.updateBasicProfile(
                    config: self.effectiveConfig,
                    accessTokenOverride: self.effectiveAccessToken,
                    payload: payload
                )
            }
            if let profile = fullProfile {
                profileSummary = PatientProfileSummaryDTO(
                    id: profile.id,
                    full_name: profile.full_name,
                    age: profile.age,
                    date_of_birth: profile.date_of_birth
                )
            }
            profileStatusMessage = "Profile updated."
        } catch {
            profileError = error.localizedDescription
        }
    }

    func addEmergencyContact(
        name: String,
        relationship: String,
        phone: String,
        email: String,
        isPrimary: Bool
    ) async {
        let payload = EmergencyContactCreatePayload(
            name: name.trimmingCharacters(in: .whitespacesAndNewlines),
            relationship: relationship.trimmingCharacters(in: .whitespacesAndNewlines),
            phone: phone.trimmingCharacters(in: .whitespacesAndNewlines),
            email: nilIfBlank(email),
            is_primary: isPrimary
        )
        await mutateProfileCollection(successMessage: "Emergency contact added.") {
            _ = try await self.backendClient.addEmergencyContact(
                config: self.effectiveConfig,
                accessTokenOverride: self.effectiveAccessToken,
                payload: payload
            )
        }
    }

    func deleteEmergencyContact(_ contact: EmergencyContactDTO) async {
        await mutateProfileCollection(successMessage: "Emergency contact removed.") {
            try await self.backendClient.deleteEmergencyContact(
                config: self.effectiveConfig,
                accessTokenOverride: self.effectiveAccessToken,
                contactID: contact.id
            )
        }
    }

    func addAllergy(
        allergen: String,
        allergyType: String,
        severity: String,
        reaction: String
    ) async {
        let payload = AllergyCreatePayload(
            allergen: allergen.trimmingCharacters(in: .whitespacesAndNewlines),
            allergy_type: allergyType,
            severity: severity,
            reaction: nilIfBlank(reaction)
        )
        await mutateProfileCollection(successMessage: "Allergy added.") {
            _ = try await self.backendClient.addAllergy(
                config: self.effectiveConfig,
                accessTokenOverride: self.effectiveAccessToken,
                payload: payload
            )
        }
    }

    func deleteAllergy(_ allergy: AllergyDTO) async {
        await mutateProfileCollection(successMessage: "Allergy removed.") {
            try await self.backendClient.deleteAllergy(
                config: self.effectiveConfig,
                accessTokenOverride: self.effectiveAccessToken,
                allergyID: allergy.id
            )
        }
    }

    func addCondition(
        name: String,
        status: String,
        diagnosedDate: String
    ) async {
        let payload = ConditionCreatePayload(
            condition_name: name.trimmingCharacters(in: .whitespacesAndNewlines),
            status: status,
            diagnosed_date: nilIfBlank(diagnosedDate)
        )
        await mutateProfileCollection(successMessage: "Condition added.") {
            _ = try await self.backendClient.addCondition(
                config: self.effectiveConfig,
                accessTokenOverride: self.effectiveAccessToken,
                payload: payload
            )
        }
    }

    func deleteCondition(_ condition: ConditionDTO) async {
        await mutateProfileCollection(successMessage: "Condition removed.") {
            try await self.backendClient.deleteCondition(
                config: self.effectiveConfig,
                accessTokenOverride: self.effectiveAccessToken,
                conditionID: condition.id
            )
        }
    }

    func addProvider(
        name: String,
        providerType: String,
        specialty: String,
        clinicName: String,
        phone: String,
        email: String,
        address: String,
        isPrimary: Bool,
        notes: String
    ) async {
        let payload = ProviderCreatePayload(
            provider_type: providerType,
            specialty: nilIfBlank(specialty),
            name: name.trimmingCharacters(in: .whitespacesAndNewlines),
            clinic_name: nilIfBlank(clinicName),
            phone: nilIfBlank(phone),
            email: nilIfBlank(email),
            address: nilIfBlank(address),
            is_primary: isPrimary,
            notes: nilIfBlank(notes)
        )
        await mutateProfileCollection(successMessage: "Provider added.") {
            _ = try await self.backendClient.addProvider(
                config: self.effectiveConfig,
                accessTokenOverride: self.effectiveAccessToken,
                payload: payload
            )
        }
    }

    func deleteProvider(_ provider: ProviderDTO) async {
        await mutateProfileCollection(successMessage: "Provider removed.") {
            try await self.backendClient.deleteProvider(
                config: self.effectiveConfig,
                accessTokenOverride: self.effectiveAccessToken,
                providerID: provider.id
            )
        }
    }

    func addFamilyHistory(
        relation: String,
        condition: String,
        ageOfOnset: String,
        isDeceased: Bool,
        notes: String
    ) async {
        let payload = FamilyHistoryCreatePayload(
            relation: relation,
            condition: condition.trimmingCharacters(in: .whitespacesAndNewlines),
            age_of_onset: Int(ageOfOnset.trimmingCharacters(in: .whitespacesAndNewlines)),
            is_deceased: isDeceased,
            notes: nilIfBlank(notes)
        )
        await mutateProfileCollection(successMessage: "Family history added.") {
            _ = try await self.backendClient.addFamilyHistory(
                config: self.effectiveConfig,
                accessTokenOverride: self.effectiveAccessToken,
                payload: payload
            )
        }
    }

    func deleteFamilyHistory(_ history: FamilyHistoryDTO) async {
        await mutateProfileCollection(successMessage: "Family history removed.") {
            try await self.backendClient.deleteFamilyHistory(
                config: self.effectiveConfig,
                accessTokenOverride: self.effectiveAccessToken,
                historyID: history.id
            )
        }
    }

    func saveLifestyle(
        smokingStatus: String,
        smokingFrequency: String,
        alcoholUse: String,
        exerciseFrequency: String,
        dietType: String,
        sleepHours: String,
        occupation: String,
        stressLevel: String
    ) async {
        let payload = LifestyleUpdatePayload(
            smoking_status: nilIfBlank(smokingStatus),
            smoking_frequency: nilIfBlank(smokingFrequency),
            alcohol_use: nilIfBlank(alcoholUse),
            exercise_frequency: nilIfBlank(exerciseFrequency),
            diet_type: nilIfBlank(dietType),
            sleep_hours: Double(sleepHours.trimmingCharacters(in: .whitespacesAndNewlines)),
            occupation: nilIfBlank(occupation),
            stress_level: nilIfBlank(stressLevel)
        )
        await mutateProfileCollection(successMessage: "Lifestyle updated.") {
            _ = try await self.backendClient.updateLifestyle(
                config: self.effectiveConfig,
                accessTokenOverride: self.effectiveAccessToken,
                payload: payload
            )
        }
    }

    func sendChatMessage() async {
        let trimmed = chatDraft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        if effectiveConfig.patientID == nil {
            do {
                try await selectFirstPatientIfNeeded()
            } catch {
                let message = "I could not find a patient profile for this session. Open Sync, confirm the backend URL, then refresh patient data."
                chatMessages.append(
                    PatientChatMessage(role: .assistant, text: message, citationCount: nil, isError: true)
                )
                lastError = error.localizedDescription
                return
            }
        }

        guard effectiveConfig.patientID != nil else {
            let message = "Select a patient before sending chat requests."
            chatMessages.append(
                PatientChatMessage(role: .assistant, text: message, citationCount: nil, isError: true)
            )
            lastError = message
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
                    conversationID: self.lastConversationID,
                    preferredLanguage: self.preferredChatLanguage
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
            let mobileToken = sanitizedToken((try keychain.readToken(account: mobileTokenAccount)) ?? "")
            if !mobileToken.isEmpty {
                return mobileToken
            }
            let webToken = sanitizedToken((try keychain.readToken(account: webTokenAccount)) ?? "")
            return webToken.isEmpty ? nil : webToken
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
            config.baseURL = migratedBackendURL(baseURL)
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

    private func migratedBackendURL(_ value: String) -> String {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed == "http://192.168.1.25:8000" {
            return SyncConfig().baseURL
        }
        return trimmed
    }

    private func loadStoredAuthState() {
        do {
            isAuthenticated = !sanitizedToken((try keychain.readToken(account: webTokenAccount)) ?? "").isEmpty
        } catch {
            isAuthenticated = false
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

    private func persistWebSession(_ response: TokenResponseDTO) throws {
        try keychain.saveToken(response.access_token, account: webTokenAccount)
        try keychain.saveToken(response.refresh_token, account: webRefreshTokenAccount)
        config.bearerToken = response.access_token
        isAuthenticated = true
    }

    private func selectFirstPatientIfNeeded(accessToken: String? = nil) async throws {
        if effectiveConfig.patientID != nil {
            return
        }
        let patients = try await backendClient.listPatients(
            config: effectiveConfig,
            accessTokenOverride: accessToken ?? effectiveAccessToken
        )
        guard let firstPatient = patients.first else {
            throw HealthSyncError.invalidConfig("No patient profile is connected to this account yet.")
        }
        config.patientIDText = String(firstPatient.id)
        profileSummary = firstPatient
        persistConfig()
    }

    private func mutateProfileCollection(
        successMessage: String,
        operation: () async throws -> Void
    ) async {
        isMutatingProfileCollection = true
        profileError = nil
        profileStatusMessage = nil
        defer { isMutatingProfileCollection = false }

        do {
            try await runWithAutoRefresh(operation)
            profileStatusMessage = successMessage
            await loadFullProfile(force: true)
        } catch {
            profileError = error.localizedDescription
        }
    }

    private func sanitizedToken(_ rawValue: String) -> String {
        var token = rawValue.filter { !$0.isWhitespace && !$0.isNewline }
        if token.hasPrefix("\""), token.hasSuffix("\""), token.count >= 2 {
            token.removeFirst()
            token.removeLast()
        }
        return token
    }

    private func nilIfBlank(_ value: String) -> String? {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }
}
