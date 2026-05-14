import SwiftUI

struct PatientProfileView: View {
    @ObservedObject var viewModel: HealthSyncViewModel
    @State private var isEditingBasics = false
    @State private var activeCollectionSheet: ProfileCollectionSheet?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    profileHeader
                    statusCard
                    sectionCard(title: "Emergency", symbolName: "cross.case.fill") {
                        addButton("Add contact") {
                            activeCollectionSheet = .emergencyContact
                        }
                        if let profile = viewModel.fullProfile, !profile.emergency_contacts.isEmpty {
                            ForEach(profile.emergency_contacts) { contact in
                                profileRow(
                                    title: contact.name,
                                    detail: "\(contact.relationship.capitalized) · \(contact.phone)",
                                    status: contact.is_primary ? "Primary" : nil,
                                    onDelete: {
                                        Task { await viewModel.deleteEmergencyContact(contact) }
                                    }
                                )
                            }
                        } else {
                            emptyState("Add an emergency contact so care details are available quickly.")
                        }
                    }
                    sectionCard(title: "Medical", symbolName: "list.bullet.clipboard.fill") {
                        HStack(spacing: 10) {
                            addButton("Add allergy") {
                                activeCollectionSheet = .allergy
                            }
                            addButton("Add condition") {
                                activeCollectionSheet = .condition
                            }
                        }
                        if let profile = viewModel.fullProfile,
                           profile.allergies.isEmpty && profile.conditions.isEmpty {
                            emptyState("No allergies or conditions are listed yet.")
                        } else {
                            ForEach(viewModel.fullProfile?.allergies ?? []) { allergy in
                                profileRow(
                                    title: allergy.allergen,
                                    detail: "\(formatValue(allergy.allergy_type)) allergy",
                                    status: formatValue(allergy.severity),
                                    onDelete: {
                                        Task { await viewModel.deleteAllergy(allergy) }
                                    }
                                )
                            }
                            ForEach(viewModel.fullProfile?.conditions ?? []) { condition in
                                profileRow(
                                    title: condition.condition_name,
                                    detail: condition.diagnosed_date ?? "No diagnosis date",
                                    status: formatValue(condition.status),
                                    onDelete: {
                                        Task { await viewModel.deleteCondition(condition) }
                                    }
                                )
                            }
                        }
                    }
                    sectionCard(title: "Care Team", symbolName: "person.2.fill") {
                        if let profile = viewModel.fullProfile, !profile.providers.isEmpty {
                            ForEach(profile.providers) { provider in
                                profileRow(
                                    title: provider.name,
                                    detail: [provider.clinic_name, provider.phone].compactMap { $0 }.joined(separator: " · "),
                                    status: provider.is_primary ? "Primary" : formatValue(provider.provider_type)
                                )
                            }
                        } else {
                            emptyState("Add doctors, pharmacies, or clinics to make records easier to interpret.")
                        }
                    }
                    sectionCard(title: "Family History", symbolName: "figure.2.and.child.holdinghands") {
                        if let profile = viewModel.fullProfile, !profile.family_history.isEmpty {
                            ForEach(profile.family_history) { item in
                                profileRow(
                                    title: item.condition,
                                    detail: item.relation.capitalized,
                                    status: item.age_of_onset.map { "Age \($0)" }
                                )
                            }
                        } else {
                            emptyState("No family history entries are listed yet.")
                        }
                    }
                    sectionCard(title: "Lifestyle", symbolName: "figure.walk") {
                        if let lifestyle = viewModel.fullProfile?.lifestyle {
                            profileRow(title: "Exercise", detail: formatOptional(lifestyle.exercise_frequency), status: nil)
                            profileRow(title: "Sleep", detail: lifestyle.sleep_hours.map { "\($0) hours" } ?? "Not set", status: nil)
                            profileRow(title: "Stress", detail: formatOptional(lifestyle.stress_level), status: nil)
                            profileRow(title: "Smoking", detail: formatOptional(lifestyle.smoking_status), status: nil)
                        } else {
                            emptyState("Lifestyle details are not set yet.")
                        }
                    }
                }
                .padding(.horizontal, 18)
                .padding(.top, 8)
                .padding(.bottom, 32)
            }
            .background(
                LinearGradient(
                    colors: [MedMemoryTheme.canvas, Color(red: 0.99, green: 0.94, blue: 0.90)],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
                .ignoresSafeArea()
            )
            .navigationTitle("Profile")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Edit") {
                        isEditingBasics = true
                    }
                    .disabled(viewModel.fullProfile == nil || viewModel.isSavingProfile)
                }
            }
            .task {
                await viewModel.loadFullProfile()
            }
            .refreshable {
                await viewModel.loadFullProfile(force: true)
            }
            .sheet(isPresented: $isEditingBasics) {
                BasicProfileEditView(viewModel: viewModel, isPresented: $isEditingBasics)
            }
            .sheet(item: $activeCollectionSheet) { sheet in
                switch sheet {
                case .emergencyContact:
                    EmergencyContactEditView(viewModel: viewModel, activeSheet: $activeCollectionSheet)
                case .allergy:
                    AllergyEditView(viewModel: viewModel, activeSheet: $activeCollectionSheet)
                case .condition:
                    ConditionEditView(viewModel: viewModel, activeSheet: $activeCollectionSheet)
                }
            }
        }
    }

    private var profileHeader: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .center, spacing: 14) {
                ZStack {
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .fill(MedMemoryTheme.accent)
                    Text(initials)
                        .font(.title3.bold())
                        .foregroundStyle(.white)
                }
                .frame(width: 58, height: 58)

                VStack(alignment: .leading, spacing: 5) {
                    Text(viewModel.fullProfile?.full_name ?? viewModel.profileSummary?.full_name ?? "Health profile")
                        .font(.title2.weight(.bold))
                        .foregroundStyle(MedMemoryTheme.textPrimary)
                    Text(profileMeta)
                        .font(.subheadline)
                        .foregroundStyle(MedMemoryTheme.textSecondary)
                }

                Spacer()

                completionBadge
            }

            if let profile = viewModel.fullProfile {
                VStack(alignment: .leading, spacing: 8) {
                    contactLine("phone.fill", profile.phone ?? "Phone not set")
                    contactLine("envelope.fill", profile.email ?? "Email not set")
                    contactLine("globe", languageName(profile.preferred_language))
                }
            }
        }
        .medMemoryCard()
    }

    private var completionBadge: some View {
        let percent = viewModel.fullProfile?.profile_completion?.overall_percentage
            ?? viewModel.profileSummary.map { _ in 0 }
            ?? 0
        return VStack(spacing: 4) {
            ZStack {
                Circle()
                    .stroke(MedMemoryTheme.accentSoft, lineWidth: 5)
                Circle()
                    .trim(from: 0, to: CGFloat(percent) / 100)
                    .stroke(MedMemoryTheme.accent, style: StrokeStyle(lineWidth: 5, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                Text("\(percent)%")
                    .font(.caption.bold())
                    .foregroundStyle(MedMemoryTheme.accent)
            }
            .frame(width: 52, height: 52)
            Text("Complete")
                .font(.caption2.weight(.semibold))
                .foregroundStyle(MedMemoryTheme.textSecondary)
                .textCase(.uppercase)
        }
    }

    @ViewBuilder
    private var statusCard: some View {
        if viewModel.isLoadingFullProfile {
            messageCard("Loading full patient profile...")
        } else if let error = viewModel.profileError {
            VStack(alignment: .leading, spacing: 10) {
                messageCard(error)
                Button("Retry") {
                    Task { await viewModel.loadFullProfile(force: true) }
                }
                .buttonStyle(MedMemorySecondaryButtonStyle())
            }
        } else if let status = viewModel.profileStatusMessage {
            messageCard(status)
        }
    }

    private func sectionCard<Content: View>(
        title: String,
        symbolName: String,
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 10) {
                Image(systemName: symbolName)
                    .foregroundStyle(MedMemoryTheme.accent)
                Text(title)
                    .font(.headline)
                    .foregroundStyle(MedMemoryTheme.textPrimary)
                Spacer()
            }
            content()
        }
        .medMemoryCard()
    }

    private func profileRow(
        title: String,
        detail: String,
        status: String?,
        onDelete: (() -> Void)? = nil
    ) -> some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(MedMemoryTheme.textPrimary)
                if !detail.isEmpty {
                    Text(detail)
                        .font(.caption)
                        .foregroundStyle(MedMemoryTheme.textSecondary)
                }
            }
            Spacer()
            if let status, !status.isEmpty {
                Text(status)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(MedMemoryTheme.textPrimary)
                    .padding(.horizontal, 9)
                    .padding(.vertical, 5)
                    .background(MedMemoryTheme.accentSoft)
                    .clipShape(Capsule())
            }
            if let onDelete {
                Button(role: .destructive, action: onDelete) {
                    Image(systemName: "trash")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.red)
                        .frame(width: 30, height: 30)
                        .background(Color.white.opacity(0.9))
                        .clipShape(Circle())
                }
                .disabled(viewModel.isMutatingProfileCollection)
            }
        }
        .padding(12)
        .background(Color.white.opacity(0.74))
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private func addButton(_ title: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Label(title, systemImage: "plus")
                .font(.caption.weight(.semibold))
                .foregroundStyle(MedMemoryTheme.textPrimary)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 10)
                .background(Color.white.opacity(0.82))
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
        .disabled(viewModel.fullProfile == nil || viewModel.isMutatingProfileCollection)
    }

    private func emptyState(_ text: String) -> some View {
        Text(text)
            .font(.subheadline)
            .foregroundStyle(MedMemoryTheme.textSecondary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(12)
            .background(Color.white.opacity(0.68))
            .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
    }

    private func messageCard(_ text: String) -> some View {
        Text(text)
            .font(.subheadline)
            .foregroundStyle(MedMemoryTheme.textSecondary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
            .background(Color.white.opacity(0.78))
            .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func contactLine(_ symbolName: String, _ text: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: symbolName)
                .font(.caption)
                .foregroundStyle(MedMemoryTheme.accent)
                .frame(width: 18)
            Text(text)
                .font(.caption)
                .foregroundStyle(MedMemoryTheme.textSecondary)
        }
    }

    private var initials: String {
        guard let profile = viewModel.fullProfile else {
            return viewModel.profileSummary?.full_name
                .split(separator: " ")
                .prefix(2)
                .compactMap { $0.first }
                .map(String.init)
                .joined()
                .uppercased() ?? "?"
        }
        let first = profile.first_name.first.map(String.init) ?? ""
        let last = profile.last_name.first.map(String.init) ?? ""
        return (first + last).isEmpty ? "?" : (first + last).uppercased()
    }

    private var profileMeta: String {
        let profile = viewModel.fullProfile
        let age = profile?.age.map { "\($0) years old" }
        let sex = profile?.sex?.capitalized
        let blood = profile?.blood_type == "unknown" ? nil : profile?.blood_type
        let values = [age, sex, blood].compactMap { $0 }
        return values.isEmpty ? "Complete the profile to personalize MedMemory." : values.joined(separator: " · ")
    }

    private func formatOptional(_ value: String?) -> String {
        guard let value, !value.isEmpty else { return "Not set" }
        return formatValue(value)
    }

    private func formatValue(_ value: String) -> String {
        value.replacingOccurrences(of: "_", with: " ").capitalized
    }

    private func languageName(_ code: String?) -> String {
        switch code {
        case "sw":
            return "Swahili"
        case "sheng":
            return "Sheng"
        default:
            return "English"
        }
    }
}

private enum ProfileCollectionSheet: String, Identifiable {
    case emergencyContact
    case allergy
    case condition

    var id: String { rawValue }
}

private struct BasicProfileEditView: View {
    @ObservedObject var viewModel: HealthSyncViewModel
    @Binding var isPresented: Bool

    @State private var firstName = ""
    @State private var lastName = ""
    @State private var dateOfBirth = ""
    @State private var sex = ""
    @State private var bloodType = ""
    @State private var heightCM = ""
    @State private var weightKG = ""
    @State private var phone = ""
    @State private var email = ""
    @State private var address = ""
    @State private var preferredLanguage = "en"

    private let sexOptions = ["", "male", "female", "other"]
    private let bloodTypeOptions = ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "unknown"]
    private let languageOptions = ["en", "sw", "sheng"]

    var body: some View {
        NavigationStack {
            Form {
                Section("Identity") {
                    TextField("First name", text: $firstName)
                    TextField("Last name", text: $lastName)
                    TextField("Date of birth (YYYY-MM-DD)", text: $dateOfBirth)
                        .keyboardType(.numbersAndPunctuation)
                    Picker("Sex", selection: $sex) {
                        ForEach(sexOptions, id: \.self) { option in
                            Text(option.isEmpty ? "Not set" : option.capitalized).tag(option)
                        }
                    }
                    Picker("Blood type", selection: $bloodType) {
                        ForEach(bloodTypeOptions, id: \.self) { option in
                            Text(option.isEmpty ? "Not set" : option).tag(option)
                        }
                    }
                }

                Section("Vitals") {
                    TextField("Height cm", text: $heightCM)
                        .keyboardType(.decimalPad)
                    TextField("Weight kg", text: $weightKG)
                        .keyboardType(.decimalPad)
                }

                Section("Contact") {
                    TextField("Phone", text: $phone)
                        .keyboardType(.phonePad)
                    TextField("Email", text: $email)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                    TextField("Address", text: $address, axis: .vertical)
                        .lineLimit(2...4)
                }

                Section("Language") {
                    Picker("Preferred language", selection: $preferredLanguage) {
                        ForEach(languageOptions, id: \.self) { option in
                            Text(languageLabel(option)).tag(option)
                        }
                    }
                }
            }
            .navigationTitle("Edit profile")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        isPresented = false
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(viewModel.isSavingProfile ? "Saving..." : "Save") {
                        Task {
                            await viewModel.saveBasicProfile(
                                firstName: firstName,
                                lastName: lastName,
                                dateOfBirth: dateOfBirth,
                                sex: sex,
                                bloodType: bloodType,
                                heightCM: heightCM,
                                weightKG: weightKG,
                                phone: phone,
                                email: email,
                                address: address,
                                preferredLanguage: preferredLanguage
                            )
                            if viewModel.profileError == nil {
                                isPresented = false
                            }
                        }
                    }
                    .disabled(viewModel.isSavingProfile || firstName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || lastName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
            .onAppear(perform: hydrate)
        }
    }

    private func hydrate() {
        guard let profile = viewModel.fullProfile else { return }
        firstName = profile.first_name
        lastName = profile.last_name
        dateOfBirth = profile.date_of_birth ?? ""
        sex = profile.sex ?? ""
        bloodType = profile.blood_type ?? ""
        heightCM = profile.height_cm.map { String(format: "%.0f", $0) } ?? ""
        weightKG = profile.weight_kg.map { String(format: "%.1f", $0) } ?? ""
        phone = profile.phone ?? ""
        email = profile.email ?? ""
        address = profile.address ?? ""
        preferredLanguage = profile.preferred_language ?? "en"
    }

    private func languageLabel(_ code: String) -> String {
        switch code {
        case "sw":
            return "Swahili"
        case "sheng":
            return "Sheng"
        default:
            return "English"
        }
    }
}

private struct EmergencyContactEditView: View {
    @ObservedObject var viewModel: HealthSyncViewModel
    @Binding var activeSheet: ProfileCollectionSheet?

    @State private var name = ""
    @State private var relationship = ""
    @State private var phone = ""
    @State private var email = ""
    @State private var isPrimary = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Contact") {
                    TextField("Name", text: $name)
                    TextField("Relationship", text: $relationship)
                    TextField("Phone", text: $phone)
                        .keyboardType(.phonePad)
                    TextField("Email", text: $email)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                    Toggle("Primary contact", isOn: $isPrimary)
                }
            }
            .navigationTitle("Add contact")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { activeSheet = nil }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(viewModel.isMutatingProfileCollection ? "Saving..." : "Save") {
                        Task {
                            await viewModel.addEmergencyContact(
                                name: name,
                                relationship: relationship,
                                phone: phone,
                                email: email,
                                isPrimary: isPrimary
                            )
                            if viewModel.profileError == nil {
                                activeSheet = nil
                            }
                        }
                    }
                    .disabled(
                        viewModel.isMutatingProfileCollection ||
                        name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ||
                        relationship.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ||
                        phone.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                    )
                }
            }
        }
    }
}

private struct AllergyEditView: View {
    @ObservedObject var viewModel: HealthSyncViewModel
    @Binding var activeSheet: ProfileCollectionSheet?

    @State private var allergen = ""
    @State private var allergyType = "drug"
    @State private var severity = "moderate"
    @State private var reaction = ""

    private let allergyTypes = ["food", "drug", "environmental", "other"]
    private let severities = ["mild", "moderate", "severe", "life_threatening"]

    var body: some View {
        NavigationStack {
            Form {
                Section("Allergy") {
                    TextField("Allergen", text: $allergen)
                    Picker("Type", selection: $allergyType) {
                        ForEach(allergyTypes, id: \.self) { option in
                            Text(formatValue(option)).tag(option)
                        }
                    }
                    Picker("Severity", selection: $severity) {
                        ForEach(severities, id: \.self) { option in
                            Text(formatValue(option)).tag(option)
                        }
                    }
                    TextField("Reaction", text: $reaction, axis: .vertical)
                        .lineLimit(2...4)
                }
            }
            .navigationTitle("Add allergy")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { activeSheet = nil }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(viewModel.isMutatingProfileCollection ? "Saving..." : "Save") {
                        Task {
                            await viewModel.addAllergy(
                                allergen: allergen,
                                allergyType: allergyType,
                                severity: severity,
                                reaction: reaction
                            )
                            if viewModel.profileError == nil {
                                activeSheet = nil
                            }
                        }
                    }
                    .disabled(
                        viewModel.isMutatingProfileCollection ||
                        allergen.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                    )
                }
            }
        }
    }

    private func formatValue(_ value: String) -> String {
        value.replacingOccurrences(of: "_", with: " ").capitalized
    }
}

private struct ConditionEditView: View {
    @ObservedObject var viewModel: HealthSyncViewModel
    @Binding var activeSheet: ProfileCollectionSheet?

    @State private var name = ""
    @State private var status = "active"
    @State private var diagnosedDate = ""

    private let statuses = ["active", "resolved", "in_remission"]

    var body: some View {
        NavigationStack {
            Form {
                Section("Condition") {
                    TextField("Condition name", text: $name)
                    Picker("Status", selection: $status) {
                        ForEach(statuses, id: \.self) { option in
                            Text(formatValue(option)).tag(option)
                        }
                    }
                    TextField("Diagnosed date (YYYY-MM-DD)", text: $diagnosedDate)
                        .keyboardType(.numbersAndPunctuation)
                }
            }
            .navigationTitle("Add condition")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { activeSheet = nil }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(viewModel.isMutatingProfileCollection ? "Saving..." : "Save") {
                        Task {
                            await viewModel.addCondition(
                                name: name,
                                status: status,
                                diagnosedDate: diagnosedDate
                            )
                            if viewModel.profileError == nil {
                                activeSheet = nil
                            }
                        }
                    }
                    .disabled(
                        viewModel.isMutatingProfileCollection ||
                        name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                    )
                }
            }
        }
    }

    private func formatValue(_ value: String) -> String {
        value.replacingOccurrences(of: "_", with: " ").capitalized
    }
}

#Preview {
    PatientProfileView(viewModel: HealthSyncViewModel())
}
