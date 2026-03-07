import SwiftUI

struct PatientWorkspaceView: View {
    private let documents: [DemoDocumentItem] = [
        DemoDocumentItem(title: "Quest lipid panel", note: "Processed PDF · 4 pages", status: "Ready"),
        DemoDocumentItem(title: "Function Health summary", note: "Processed PDF · 2 pages", status: "Needs review")
    ]

    private let records: [DemoRecordItem] = [
        DemoRecordItem(title: "Pediatric annual checkup", type: "visit_note", summary: "Annual wellness visit with stable vitals and routine counseling."),
        DemoRecordItem(title: "LDL follow-up", type: "lab_result", summary: "LDL remains elevated but improved compared with prior panel.")
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                workspaceHeader
                quickActions
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

            Text("Mirror the web workspace using grouped lists, upload actions, and detail drill-ins instead of desktop panels.")
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

            ForEach(documents) { item in
                HStack(alignment: .top, spacing: 12) {
                    Image(systemName: "doc.text.fill")
                        .foregroundStyle(MedMemoryTheme.accent)
                        .padding(10)
                        .background(MedMemoryTheme.accentSoft)
                        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))

                    VStack(alignment: .leading, spacing: 4) {
                        Text(item.title)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(MedMemoryTheme.textPrimary)
                        Text(item.note)
                            .font(.caption)
                            .foregroundStyle(MedMemoryTheme.textSecondary)
                    }

                    Spacer()

                    Text(item.status)
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
        .medMemoryCard()
    }

    private var recordsCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            sectionHeader(
                title: "Clinical notes",
                subtitle: "Structured notes and summaries"
            )

            ForEach(records) { record in
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text(record.title)
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(MedMemoryTheme.textPrimary)
                        Spacer()
                        Text(record.type)
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(MedMemoryTheme.textSecondary)
                            .textCase(.uppercase)
                    }

                    Text(record.summary)
                        .font(.caption)
                        .foregroundStyle(MedMemoryTheme.textSecondary)
                }
                .padding(14)
                .background(Color.white.opacity(0.72))
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
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
}
