import SwiftUI

struct PatientWorkspaceView: View {
    @ObservedObject var viewModel: HealthSyncViewModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                workspaceHeader
                quickActions
                dataStatusCard
                documentsCard
                recordsCard
            }
            .padding(.horizontal, 18)
            .padding(.top, 8)
            .padding(.bottom, 32)
        }
        .background(
            LinearGradient(
                colors: [MedMemoryTheme.canvas, Color(red: 0.99, green: 0.94, blue: 0.9)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
        )
        .navigationTitle("Workspace")
        .navigationBarTitleDisplayMode(.inline)
    }

    private var workspaceHeader: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Patient workspace")
                .font(.caption.weight(.semibold))
                .foregroundStyle(MedMemoryTheme.accent)
                .textCase(.uppercase)

            Text("Records and documents")
                .font(.system(size: 32, weight: .bold, design: .serif))
                .foregroundStyle(MedMemoryTheme.textPrimary)

            Text(viewModel.profileSummary.map { "Documents and notes for \($0.full_name)." } ?? "Mirror the web workspace using grouped lists, upload actions, and detail drill-ins instead of desktop panels.")
                .font(.subheadline)
                .foregroundStyle(MedMemoryTheme.textSecondary)
        }
        .medMemoryCard()
    }

    private var quickActions: some View {
        HStack(spacing: 12) {
            Button("Upload document") {}
                .buttonStyle(MedMemoryPrimaryButtonStyle())

            Button("Add record") {}
                .buttonStyle(MedMemorySecondaryButtonStyle())
        }
    }

    private var documentsCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionHeader(
                title: "Documents",
                subtitle: "Processed reports and uploaded files"
            )

            if viewModel.recentDocuments.isEmpty {
                emptyStateCard("No documents loaded yet. Connect the backend in the Sync tab, then refresh patient data.")
            } else {
                ForEach(viewModel.recentDocuments.prefix(5)) { item in
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: "doc.text.fill")
                            .foregroundStyle(MedMemoryTheme.accent)
                            .padding(10)
                            .background(MedMemoryTheme.accentSoft)
                            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))

                        VStack(alignment: .leading, spacing: 4) {
                            Text(item.title ?? item.original_filename)
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(MedMemoryTheme.textPrimary)
                            Text(documentSubtitle(for: item))
                                .font(.caption)
                                .foregroundStyle(MedMemoryTheme.textSecondary)
                        }

                        Spacer()

                        Text(documentStatus(for: item))
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(MedMemoryTheme.textPrimary)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(Color.white.opacity(0.78))
                            .clipShape(Capsule())
                    }
                    .padding(14)
                    .background(Color.white.opacity(0.72))
                    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                }
            }
        }
        .medMemoryCard()
    }

    private var recordsCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionHeader(
                title: "Clinical notes",
                subtitle: "Structured notes and summaries"
            )

            if viewModel.recentRecords.isEmpty {
                emptyStateCard("No clinical notes loaded yet. Once patient data is connected, recent notes will appear here.")
            } else {
                ForEach(viewModel.recentRecords.prefix(5)) { record in
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text(record.title)
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(MedMemoryTheme.textPrimary)
                            Spacer()
                            Text(record.record_type ?? "general")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(MedMemoryTheme.textSecondary)
                                .textCase(.uppercase)
                        }

                        Text(record.content)
                            .font(.caption)
                            .foregroundStyle(MedMemoryTheme.textSecondary)
                            .lineLimit(3)
                    }
                    .padding(14)
                    .background(Color.white.opacity(0.72))
                    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                }
            }
        }
        .medMemoryCard()
    }

    private func sectionHeader(title: String, subtitle: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.headline)
                .foregroundStyle(MedMemoryTheme.textPrimary)
            Text(subtitle)
                .font(.caption)
                .foregroundStyle(MedMemoryTheme.textSecondary)
        }
    }

    private var dataStatusCard: some View {
        Group {
            if viewModel.isLoadingPatientData {
                emptyStateCard("Loading patient documents and records from MedMemory.")
            } else if let error = viewModel.patientDataError {
                emptyStateCard(error)
            }
        }
    }

    private func documentSubtitle(for item: DocumentItemDTO) -> String {
        let pages = item.page_count.map { "\($0) page(s)" } ?? "Unknown pages"
        return "\(item.document_type) · \(pages)"
    }

    private func documentStatus(for item: DocumentItemDTO) -> String {
        if item.is_processed {
            return "Ready"
        }
        return item.processing_status.replacingOccurrences(of: "_", with: " ").capitalized
    }

    private func emptyStateCard(_ message: String) -> some View {
        Text(message)
            .font(.subheadline)
            .foregroundStyle(MedMemoryTheme.textSecondary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .background(Color.white.opacity(0.72))
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}

#Preview {
    NavigationStack {
        PatientWorkspaceView(viewModel: HealthSyncViewModel())
    }
}
