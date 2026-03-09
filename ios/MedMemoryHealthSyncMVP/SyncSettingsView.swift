import SwiftUI

struct SyncSettingsView: View {
    @ObservedObject var viewModel: HealthSyncViewModel

    var body: some View {
        Form {
            Section("MedMemory backend") {
                TextField("Backend URL (use LAN IP)", text: $viewModel.config.baseURL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.URL)

                TextField("Patient ID", text: $viewModel.config.patientIDText)
                    .keyboardType(.numberPad)

                SecureField("Access token override (optional)", text: $viewModel.config.bearerToken)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()

                Text(viewModel.accessTokenSourceDescription)
                    .font(.caption)
                    .foregroundStyle(.secondary)

                LabeledContent("Token suffix") {
                    Text(viewModel.accessTokenFingerprint)
                        .font(.caption.monospaced())
                        .foregroundStyle(.secondary)
                }

                Stepper(value: $viewModel.config.daysBack, in: 1...365) {
                    Text("Days to sync: \(viewModel.config.daysBack)")
                }

                if let normalized = viewModel.config.normalizedAPIBaseURL?.absoluteString {
                    LabeledContent("API base") {
                        Text(normalized)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.trailing)
                    }
                }
            }

            Section("Apple Health") {
                Button(viewModel.isAuthorizing ? "Requesting access…" : "Request step access") {
                    Task { await viewModel.requestHealthAccess() }
                }
                .disabled(viewModel.isAuthorizing || viewModel.isSyncing)

                Text("Grant read access for step count on first run.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Section("Mobile token") {
                Button(viewModel.isIssuingMobileToken ? "Issuing mobile token…" : "Issue patient mobile token") {
                    Task { await viewModel.issueMobileToken() }
                }
                .buttonStyle(MedMemorySecondaryButtonStyle())
                .disabled(viewModel.isIssuingMobileToken || viewModel.isSyncing)

                Button("Clear stored mobile token") {
                    viewModel.clearMobileToken()
                }
                .buttonStyle(MedMemorySecondaryButtonStyle())
                .disabled(viewModel.isIssuingMobileToken || viewModel.isSyncing)

                if viewModel.hasStoredMobileToken {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Stored in Keychain")
                            .font(.subheadline.weight(.semibold))
                        Text("Scopes: \(viewModel.mobileTokenScopes.joined(separator: ", "))")
                            .font(.caption)
                        if let expiresAt = viewModel.mobileTokenExpiresAt {
                            Text("Expires: \(expiresAt.formatted(date: .abbreviated, time: .shortened))")
                                .font(.caption)
                        }
                    }
                } else {
                    Text("No mobile token is currently stored in Keychain. You can paste a fresh token in the field above to override auth for debugging.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Section("Sync") {
                Button(viewModel.isSyncing ? "Syncing…" : "Sync now") {
                    Task { await viewModel.syncNow() }
                }
                .buttonStyle(MedMemoryPrimaryButtonStyle())
                .disabled(viewModel.isSyncing || viewModel.isAuthorizing)

                Button("Test auth with current token") {
                    Task { await viewModel.probeAuth() }
                }
                .buttonStyle(MedMemorySecondaryButtonStyle())
                .disabled(viewModel.isSyncing || viewModel.isAuthorizing || viewModel.isLoadingPatientData)

                Button(viewModel.isLoadingPatientData ? "Refreshing patient data…" : "Refresh patient data") {
                    Task { await viewModel.loadPatientExperience(force: true) }
                }
                .buttonStyle(MedMemorySecondaryButtonStyle())
                .disabled(viewModel.isSyncing || viewModel.isAuthorizing || viewModel.isLoadingPatientData)

                if viewModel.lastError != nil {
                    Button("Retry sync") {
                        Task { await viewModel.retryLastSync() }
                    }
                    .buttonStyle(MedMemorySecondaryButtonStyle())
                    .disabled(viewModel.isSyncing || viewModel.isAuthorizing)
                }

                LabeledContent("Status") {
                    Text(viewModel.statusMessage)
                        .foregroundStyle(viewModel.lastError == nil ? Color.secondary : Color.red)
                }

                if let lastResponse = viewModel.lastResponse {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Last sync result")
                            .font(.subheadline.weight(.semibold))
                        Text("Received \(lastResponse.received_samples) samples (\(lastResponse.unique_days_received) unique days)")
                        Text("Inserted \(lastResponse.inserted_days), updated \(lastResponse.updated_days), unchanged \(lastResponse.unchanged_days)")
                        Text("Connection status: \(lastResponse.connection_status)")
                        if let lastSynced = lastResponse.last_synced_at {
                            Text("Last synced: \(lastSynced)")
                        }
                    }
                    .font(.caption)
                }

                if let error = viewModel.lastError {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Last error")
                            .font(.subheadline.weight(.semibold))
                        Text(error)
                            .foregroundStyle(.red)
                    }
                    .font(.caption)
                }

                if let authProbeMessage = viewModel.authProbeMessage {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Auth probe")
                            .font(.subheadline.weight(.semibold))
                        Text(authProbeMessage)
                            .foregroundStyle(
                                authProbeMessage.hasPrefix("Auth OK")
                                    ? AnyShapeStyle(.secondary)
                                    : AnyShapeStyle(Color.red)
                            )
                    }
                    .font(.caption)
                }
            }

            if !viewModel.lastSamplesPreview.isEmpty {
                Section("Latest fetched days (preview)") {
                    ForEach(viewModel.lastSamplesPreview.reversed()) { sample in
                        HStack {
                            VStack(alignment: .leading) {
                                Text(sample.sampleDate, format: Date.FormatStyle().month(.abbreviated).day())
                                Text(sample.timeZoneIdentifier)
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            Text("\(sample.stepCount)")
                                .font(.headline)
                            Text("steps")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
        .navigationTitle("Sync")
        .navigationBarTitleDisplayMode(.inline)
    }
}
