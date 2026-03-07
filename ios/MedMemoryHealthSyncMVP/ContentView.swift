import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel = HealthSyncViewModel()

    var body: some View {
        NavigationStack {
            TabView {
                PatientDashboardView(viewModel: viewModel)
                    .tabItem {
                        Label("Dashboard", systemImage: "square.grid.2x2.fill")
                    }

                PatientChatPrototypeView()
                    .tabItem {
                        Label("Chat", systemImage: "bubble.left.and.bubble.right.fill")
                    }

                PatientWorkspaceView()
                    .tabItem {
                        Label("Workspace", systemImage: "folder.fill")
                    }

                SyncSettingsView(viewModel: viewModel)
                    .tabItem {
                        Label("Sync", systemImage: "heart.text.square.fill")
                    }
            }
        }
    }
}

#Preview {
    ContentView()
}
