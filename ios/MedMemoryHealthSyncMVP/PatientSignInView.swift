import SwiftUI

struct PatientSignInView: View {
    @ObservedObject var viewModel: HealthSyncViewModel
    @State private var email = ""
    @State private var password = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                header
                signInCard
            }
            .padding(.horizontal, 22)
            .padding(.top, 64)
            .padding(.bottom, 48)
        }
        .background(
            LinearGradient(
                colors: [MedMemoryTheme.canvas, Color(red: 0.99, green: 0.94, blue: 0.9)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
        )
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("MedMemory")
                .font(.caption.weight(.semibold))
                .foregroundStyle(MedMemoryTheme.accent)
                .textCase(.uppercase)
            Text("Sign in to your patient workspace")
                .font(.system(size: 34, weight: .bold, design: .serif))
                .foregroundStyle(MedMemoryTheme.textPrimary)
            Text("Use the same email and password as the patient web app.")
                .font(.subheadline)
                .foregroundStyle(MedMemoryTheme.textSecondary)
        }
        .medMemoryCard()
    }

    private var signInCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Patient sign in")
                .font(.headline)
                .foregroundStyle(MedMemoryTheme.textPrimary)

            TextField("Email", text: $email)
                .keyboardType(.emailAddress)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .textContentType(.username)
                .padding(14)
                .background(Color.white.opacity(0.86))
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))

            SecureField("Password", text: $password)
                .textContentType(.password)
                .padding(14)
                .background(Color.white.opacity(0.86))
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))

            TextField("Backend URL", text: $viewModel.config.baseURL)
                .keyboardType(.URL)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .font(.caption)
                .padding(14)
                .background(Color.white.opacity(0.72))
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))

            Button("Use this Mac backend") {
                viewModel.config.baseURL = "http://127.0.0.1:8000"
            }
            .font(.caption.weight(.semibold))
            .foregroundStyle(MedMemoryTheme.accent)
            .disabled(viewModel.isSigningIn)

            if let error = viewModel.authError {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .fixedSize(horizontal: false, vertical: true)
            }

            Button(viewModel.isSigningIn ? "Signing in..." : "Sign in") {
                Task { await viewModel.signIn(email: email, password: password) }
            }
            .buttonStyle(MedMemoryPrimaryButtonStyle())
            .disabled(viewModel.isSigningIn || !formIsValid)
        }
        .medMemoryCard()
    }

    private var formIsValid: Bool {
        email.trimmingCharacters(in: .whitespacesAndNewlines).contains("@") &&
        !password.isEmpty &&
        viewModel.config.normalizedAPIBaseURL != nil
    }
}

#Preview {
    PatientSignInView(viewModel: HealthSyncViewModel())
}
