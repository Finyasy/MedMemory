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

struct DemoChatMessage: Identifiable {
    let id = UUID()
    let role: MessageRole
    let text: String

    enum MessageRole {
        case user
        case assistant
    }
}

struct DemoDocumentItem: Identifiable {
    let id = UUID()
    let title: String
    let note: String
    let status: String
}

struct DemoRecordItem: Identifiable {
    let id = UUID()
    let title: String
    let type: String
    let summary: String
}
