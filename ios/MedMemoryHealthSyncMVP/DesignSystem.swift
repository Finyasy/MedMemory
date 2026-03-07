import SwiftUI

enum MedMemoryTheme {
    static let canvas = Color(red: 0.97, green: 0.95, blue: 0.92)
    static let card = Color.white.opacity(0.78)
    static let cardStrong = Color.white.opacity(0.92)
    static let accent = Color(red: 0.89, green: 0.47, blue: 0.24)
    static let accentSoft = Color(red: 0.98, green: 0.91, blue: 0.84)
    static let textPrimary = Color(red: 0.22, green: 0.17, blue: 0.15)
    static let textSecondary = Color(red: 0.44, green: 0.37, blue: 0.33)
    static let border = Color(red: 0.92, green: 0.82, blue: 0.74)
    static let success = Color(red: 0.23, green: 0.55, blue: 0.39)
    static let warning = Color(red: 0.75, green: 0.43, blue: 0.22)
}

struct MedMemoryCardModifier: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding(18)
            .background(MedMemoryTheme.cardStrong)
            .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .stroke(MedMemoryTheme.border.opacity(0.9), lineWidth: 1)
            )
    }
}

extension View {
    func medMemoryCard() -> some View {
        modifier(MedMemoryCardModifier())
    }
}

struct MedMemoryPrimaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .fill(MedMemoryTheme.accent.opacity(configuration.isPressed ? 0.82 : 1))
            )
            .scaleEffect(configuration.isPressed ? 0.98 : 1)
            .animation(.easeOut(duration: 0.15), value: configuration.isPressed)
    }
}

struct MedMemorySecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(MedMemoryTheme.textPrimary)
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(Color.white.opacity(configuration.isPressed ? 0.74 : 0.9))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .stroke(MedMemoryTheme.border, lineWidth: 1)
            )
    }
}

