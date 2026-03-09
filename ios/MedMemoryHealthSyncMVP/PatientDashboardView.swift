import SwiftUI

struct PatientDashboardView: View {
    @ObservedObject var viewModel: HealthSyncViewModel
    @State private var selectedSection: PatientSection = .overview

    private var summaryCards: [DashboardSummaryCard] {
        let trackedMetrics = viewModel.dashboardHighlights?.summary.tracked_metrics ?? 0
        let syncedDays = viewModel.appleHealthStatus?.total_synced_days ?? 0
        let latestSteps = viewModel.appleHealthTrend?.latest_step_count ?? 0
        return [
            DashboardSummaryCard(
                title: "Records",
                value: "\(viewModel.recentRecords.count)",
                note: "\(viewModel.recentDocuments.count) document(s) available",
                symbolName: "doc.text"
            ),
            DashboardSummaryCard(
                title: "Signals",
                value: syncedDays == 0 ? "0" : "\(syncedDays)",
                note: latestSteps == 0 ? "No Apple Health steps yet" : "\(latestSteps) latest steps",
                symbolName: "waveform.path.ecg"
            ),
            DashboardSummaryCard(
                title: "Highlights",
                value: trackedMetrics == 0 ? "0" : "\(trackedMetrics)",
                note: "Grounded MedGemma-backed insights",
                symbolName: "sparkles"
            )
        ]
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                header
                sectionPicker

                switch selectedSection {
                case .overview:
                    overviewSection
                case .monitoring:
                    monitoringSection
                case .workspace:
                    workspaceSection
                }
            }
            .padding(.horizontal, 18)
            .padding(.top, 8)
            .padding(.bottom, 32)
        }
        .background(
            LinearGradient(
                colors: [MedMemoryTheme.canvas, Color(red: 0.99, green: 0.93, blue: 0.88)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
        )
        .navigationTitle("MedMemory")
        .navigationBarTitleDisplayMode(.inline)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Patient overview")
                .font(.caption.weight(.semibold))
                .foregroundStyle(MedMemoryTheme.accent)
                .textCase(.uppercase)

            Text("Your health dashboard")
                .font(.system(size: 34, weight: .bold, design: .serif))
                .foregroundStyle(MedMemoryTheme.textPrimary)

            Text(viewModel.profileSummary.map { "Track records, trends, and grounded answers for \($0.full_name)." } ?? "Track records, trends, and grounded answers in one place.")
                .font(.subheadline)
                .foregroundStyle(MedMemoryTheme.textSecondary)
        }
        .medMemoryCard()
    }

    private var sectionPicker: some View {
        Picker("Patient sections", selection: $selectedSection) {
            ForEach(PatientSection.allCases) { section in
                Text(section.rawValue).tag(section)
            }
        }
        .pickerStyle(.segmented)
    }

    private var overviewSection: some View {
        VStack(alignment: .leading, spacing: 18) {
            dataStatusCard

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(summaryCards) { card in
                        VStack(alignment: .leading, spacing: 10) {
                            Image(systemName: card.symbolName)
                                .font(.headline)
                                .foregroundStyle(MedMemoryTheme.accent)
                            Text(card.title)
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(MedMemoryTheme.textSecondary)
                                .textCase(.uppercase)
                            Text(card.value)
                                .font(.title3.bold())
                                .foregroundStyle(MedMemoryTheme.textPrimary)
                            Text(card.note)
                                .font(.caption)
                                .foregroundStyle(MedMemoryTheme.textSecondary)
                        }
                        .frame(width: 150, alignment: .leading)
                        .medMemoryCard()
                    }
                }
            }

            appleHealthCard
            highlightsCard
        }
    }

    private var monitoringSection: some View {
        VStack(alignment: .leading, spacing: 18) {
            statusCard(
                title: "Watchlist",
                body: "Tracked metrics: \(viewModel.dashboardHighlights?.summary.tracked_metrics ?? 0). Native watchlist screens should mirror the web monitoring section, but use drill-in cards instead of sidebars."
            )
            statusCard(
                title: "Alerts",
                body: "Use local notification-friendly alert summaries and a clear acknowledge flow. Out-of-range highlights: \(viewModel.dashboardHighlights?.summary.out_of_range ?? 0)."
            )
        }
    }

    private var workspaceSection: some View {
        VStack(alignment: .leading, spacing: 18) {
            statusCard(
                title: "Documents",
                body: "Available now: \(viewModel.recentDocuments.count) document(s). This tab should eventually own camera scan, upload progress, and document previews."
            )
            statusCard(
                title: "Records",
                body: "Available now: \(viewModel.recentRecords.count) clinical note(s). Use grouped lists and detail sheets rather than desktop-style dual panels."
            )
        }
    }

    private var dataStatusCard: some View {
        Group {
            if viewModel.isLoadingPatientData {
                statusCard(title: "Loading", body: "Fetching profile, highlights, documents, and Apple Health state from MedMemory.")
            } else if let error = viewModel.patientDataError {
                statusCard(title: "Backend connection needed", body: error)
            }
        }
    }

    private var appleHealthCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Apple Health")
                        .font(.headline)
                        .foregroundStyle(MedMemoryTheme.textPrimary)
                    Text("Native-only sync surface")
                        .font(.caption)
                        .foregroundStyle(MedMemoryTheme.textSecondary)
                }
                Spacer()
                Text((viewModel.appleHealthStatus?.status ?? viewModel.lastResponse?.connection_status ?? "Disconnected").capitalized)
                    .font(.caption.weight(.semibold))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(MedMemoryTheme.accentSoft)
                    .clipShape(Capsule())
            }

            if let trend = viewModel.appleHealthTrend, let latestSteps = trend.latest_step_count {
                Text("Latest steps: \(latestSteps). \(trend.points.count) day(s) loaded for dashboard trends.")
                .font(.subheadline)
                .foregroundStyle(MedMemoryTheme.textSecondary)
            } else if let response = viewModel.lastResponse {
                Text("Last sync inserted \(response.inserted_days) day(s), updated \(response.updated_days) day(s).")
                    .font(.subheadline)
                    .foregroundStyle(MedMemoryTheme.textSecondary)
            } else {
                Text("HealthKit sync is configured as a dedicated native tab, then reflected back into dashboard trends.")
                    .font(.subheadline)
                    .foregroundStyle(MedMemoryTheme.textSecondary)
            }
        }
        .medMemoryCard()
    }

    private var highlightsCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Highlights")
                .font(.headline)
                .foregroundStyle(MedMemoryTheme.textPrimary)

            if let highlights = viewModel.dashboardHighlights?.highlights, !highlights.isEmpty {
                VStack(spacing: 10) {
                    ForEach(highlights.prefix(3)) { item in
                        highlightRow(
                            item.metric_name,
                            highlightBody(for: item)
                        )
                    }
                }
            } else {
                Text("Mirror the web dashboard hierarchy, not the exact panel layout: summary first, then trends, then actions.")
                    .font(.subheadline)
                    .foregroundStyle(MedMemoryTheme.textSecondary)

                VStack(spacing: 10) {
                    highlightRow("Grounded answers", "Patient chat should preserve citations and refusal behavior.")
                    highlightRow("Trend cards", "Apple Health and lab trends should share one visual language.")
                    highlightRow("Fast actions", "Upload document, ask question, sync iPhone.")
                }
            }
        }
        .medMemoryCard()
    }

    private func highlightRow(_ title: String, _ body: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Circle()
                .fill(MedMemoryTheme.accent)
                .frame(width: 8, height: 8)
                .padding(.top, 6)
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(MedMemoryTheme.textPrimary)
                Text(body)
                    .font(.caption)
                    .foregroundStyle(MedMemoryTheme.textSecondary)
            }
            Spacer()
        }
        .padding(12)
        .background(Color.white.opacity(0.72))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func statusCard(title: String, body: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.headline)
                .foregroundStyle(MedMemoryTheme.textPrimary)
            Text(body)
                .font(.subheadline)
                .foregroundStyle(MedMemoryTheme.textSecondary)
        }
        .medMemoryCard()
    }

    private func highlightBody(for item: HighlightItemDTO) -> String {
        let valueText = item.value ?? item.numeric_value.map { String($0) } ?? "No value"
        let unitText = item.unit.map { " \($0)" } ?? ""
        let statusText = item.status.replacingOccurrences(of: "_", with: " ")
        return "\(valueText)\(unitText) · \(statusText.capitalized)"
    }
}

#Preview {
    NavigationStack {
        PatientDashboardView(viewModel: HealthSyncViewModel())
    }
}
