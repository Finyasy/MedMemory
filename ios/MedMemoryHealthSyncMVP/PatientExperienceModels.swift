import Foundation

struct DashboardSummaryCard: Identifiable {
    let id = UUID()
    let title: String
    let value: String
    let note: String
    let symbolName: String
}

enum PatientSection: String, CaseIterable, Identifiable {
    case overview = "Overview"
    case monitoring = "Monitoring"
    case workspace = "Workspace"

    var id: String { rawValue }
}

struct PatientChatMessage: Identifiable {
    let id = UUID()
    let role: MessageRole
    let text: String
    let citationCount: Int?
    let isError: Bool

    enum MessageRole {
        case user
        case assistant
    }
}
