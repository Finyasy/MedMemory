import Foundation
import SwiftUI

@MainActor
final class HealthSyncViewModel: ObservableObject {
    @Published var config = SyncConfig()
    @Published var authorizationRequested = false
    @Published var isAuthorizing = false
    @Published var isSyncing = false
    @Published var lastError: String?
    @Published var statusMessage: String = "Ready"
    @Published var lastResponse: AppleHealthStepsSyncResponseDTO?
    @Published var lastSamplesPreview: [DailyStepSample] = []
    @Published var lastSyncStartedAt: Date?

    private let healthKit = HealthKitManager()
    private let backendClient = MedMemoryBackendClient()
    private let defaults = UserDefaults.standard

    init() {
        loadSavedConfig()
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
            let response = try await backendClient.syncDailySteps(config: config, samples: samples)
            lastResponse = response
            statusMessage = "Sync complete: \(response.inserted_days) inserted, \(response.updated_days) updated."
        } catch {
            lastError = error.localizedDescription
            statusMessage = "Sync failed."
        }
    }

    func retryLastSync() async {
        await syncNow()
    }

    private func persistConfig() {
        defaults.set(config.baseURL, forKey: "healthsync.baseURL")
        defaults.set(config.patientIDText, forKey: "healthsync.patientIDText")
        defaults.set(config.bearerToken, forKey: "healthsync.bearerToken")
        defaults.set(config.daysBack, forKey: "healthsync.daysBack")
    }

    private func loadSavedConfig() {
        if let baseURL = defaults.string(forKey: "healthsync.baseURL"), !baseURL.isEmpty {
            config.baseURL = baseURL
        }
        if let patientIDText = defaults.string(forKey: "healthsync.patientIDText"), !patientIDText.isEmpty {
            config.patientIDText = patientIDText
        }
        if let bearerToken = defaults.string(forKey: "healthsync.bearerToken"), !bearerToken.isEmpty {
            config.bearerToken = bearerToken
        }
        let daysBack = defaults.integer(forKey: "healthsync.daysBack")
        if daysBack > 0 {
            config.daysBack = min(max(daysBack, 1), 365)
        }
    }
}
