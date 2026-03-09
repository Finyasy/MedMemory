import SwiftUI

struct PatientChatView: View {
    @ObservedObject var viewModel: HealthSyncViewModel

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: 14) {
                    ForEach(viewModel.chatMessages) { message in
                        messageBubble(message)
                    }
                }
                .padding(18)
            }

            VStack(spacing: 10) {
                HStack {
                    Image(systemName: "sparkles")
                        .foregroundStyle(MedMemoryTheme.accent)
                    Text(viewModel.isSendingChat ? "Thinking…" : "Grounded patient chat")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(MedMemoryTheme.textSecondary)
                    Spacer()
                }

                HStack(spacing: 12) {
                    TextField("Message MedMemory...", text: $viewModel.chatDraft, axis: .vertical)
                        .foregroundStyle(MedMemoryTheme.textPrimary)
                        .lineLimit(1...4)
                    Button {
                        Task { await viewModel.sendChatMessage() }
                    } label: {
                        Image(systemName: "paperplane.fill")
                            .foregroundStyle(.white)
                            .padding(10)
                            .background(MedMemoryTheme.accent)
                            .clipShape(Circle())
                    }
                    .disabled(viewModel.isSendingChat || viewModel.chatDraft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 12)
                .background(Color.white.opacity(0.92))
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            }
            .padding(18)
            .background(.ultraThinMaterial)
        }
        .background(MedMemoryTheme.canvas.ignoresSafeArea())
        .navigationTitle("Chat")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func messageBubble(_ message: PatientChatMessage) -> some View {
        HStack {
            if message.role == .assistant {
                VStack(alignment: .leading, spacing: 8) {
                    Text(message.text)
                        .font(.body)
                        .foregroundStyle(MedMemoryTheme.textPrimary)

                    HStack(spacing: 8) {
                        if message.isError {
                            Text("Error")
                        } else {
                            Text("Grounded")
                            if let citationCount = message.citationCount, citationCount > 0 {
                                Text("\(citationCount) source(s)")
                            }
                        }
                    }
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(message.isError ? .red : MedMemoryTheme.success)
                }
                .padding(14)
                .background(Color.white.opacity(0.92))
                .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
                Spacer(minLength: 36)
            } else {
                Spacer(minLength: 36)
                Text(message.text)
                    .font(.body)
                    .foregroundStyle(.white)
                    .padding(14)
                    .background(MedMemoryTheme.accent)
                    .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
            }
        }
    }
}

#Preview {
    NavigationStack {
        PatientChatView(viewModel: HealthSyncViewModel())
    }
}
