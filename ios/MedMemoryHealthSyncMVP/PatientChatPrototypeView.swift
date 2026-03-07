import SwiftUI

struct PatientChatPrototypeView: View {
    private let messages: [DemoChatMessage] = [
        DemoChatMessage(
            role: .assistant,
            text: "Ask about a report, lab value, medication, or date. I will only use what is in the record."
        ),
        DemoChatMessage(
            role: .user,
            text: "Summarize my latest document in short sentences."
        ),
        DemoChatMessage(
            role: .assistant,
            text: "From your records: the latest document summary should stay grounded, cited, and concise."
        )
    ]

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: 14) {
                    ForEach(messages) { message in
                        messageBubble(message)
                    }
                }
                .padding(18)
            }

            VStack(spacing: 10) {
                HStack {
                    Image(systemName: "sparkles")
                        .foregroundStyle(MedMemoryTheme.accent)
                    Text("Grounded patient chat")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(MedMemoryTheme.textSecondary)
                    Spacer()
                }

                HStack(spacing: 12) {
                    Text("Message MedMemory...")
                        .foregroundStyle(MedMemoryTheme.textSecondary)
                    Spacer()
                    Image(systemName: "paperplane.fill")
                        .foregroundStyle(.white)
                        .padding(10)
                        .background(MedMemoryTheme.accent)
                        .clipShape(Circle())
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

    private func messageBubble(_ message: DemoChatMessage) -> some View {
        HStack {
            if message.role == .assistant {
                VStack(alignment: .leading, spacing: 8) {
                    Text(message.text)
                        .font(.body)
                        .foregroundStyle(MedMemoryTheme.textPrimary)

                    HStack(spacing: 8) {
                        Text("Grounded")
                        Text("Cited")
                    }
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(MedMemoryTheme.success)
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

