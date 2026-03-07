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

                SecureField("Bearer token", text: $viewModel.config.bearerToken)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()

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

            Section("Sync") {
                Button(viewModel.isSyncing ? "Syncing…" : "Sync now") {
                    Task { await viewModel.syncNow() }
                }
                .buttonStyle(MedMemoryPrimaryButtonStyle())
                .disabled(viewModel.isSyncing || viewModel.isAuthorizing)

                if viewModel.lastError != nil {
                    Button("Retry sync") {
                        Task { await viewModel.retryLastSync() }
                    }
                    .buttonStyle(MedMemorySecondaryButtonStyle())
                    .disabled(viewModel.isSyncing || viewModel.isAuthorizing)
                }

                LabeledContent("Status") {
                    Text(viewModel.statusMessage)
                        .foregroundStyle(viewModel.lastError == nil ? .secondary : .red)
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

