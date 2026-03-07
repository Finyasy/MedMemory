import SwiftUI

struct PatientDashboardView: View {
    @ObservedObject var viewModel: HealthSyncViewModel
    @State private var selectedSection: PatientSection = .overview

    private var summaryCards: [DashboardSummaryCard] {
        [
            DashboardSummaryCard(title: "Records", value: "12", note: "Clinical notes and uploads", symbolName: "doc.text"),
            DashboardSummaryCard(title: "Signals", value: viewModel.lastResponse == nil ? "0" : "1", note: "Apple Health connected", symbolName: "waveform.path.ecg"),
            DashboardSummaryCard(title: "Chat", value: "Grounded", note: "MedGemma-backed answers", symbolName: "sparkles")
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

            Text("Track records, trends, and grounded answers in one place.")
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
                body: "Native watchlist screens should mirror the web monitoring section, but use drill-in cards instead of sidebars."
            )
            statusCard(
                title: "Alerts",
                body: "Use local notification-friendly alert summaries and a clear acknowledge flow."
            )
        }
    }

    private var workspaceSection: some View {
        VStack(alignment: .leading, spacing: 18) {
            statusCard(
                title: "Documents",
                body: "This tab should eventually own camera scan, upload progress, and document previews."
            )
            statusCard(
                title: "Records",
                body: "Use grouped lists and detail sheets rather than desktop-style dual panels."
            )
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
                Text(viewModel.lastResponse?.connection_status.capitalized ?? "Disconnected")
                    .font(.caption.weight(.semibold))
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(MedMemoryTheme.accentSoft)
                    .clipShape(Capsule())
            }

            if let response = viewModel.lastResponse {
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

            Text("Mirror the web dashboard hierarchy, not the exact panel layout: summary first, then trends, then actions.")
                .font(.subheadline)
                .foregroundStyle(MedMemoryTheme.textSecondary)

            VStack(spacing: 10) {
                highlightRow("Grounded answers", "Patient chat should preserve citations and refusal behavior.")
                highlightRow("Trend cards", "Apple Health and lab trends should share one visual language.")
                highlightRow("Fast actions", "Upload document, ask question, sync iPhone.")
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
}

