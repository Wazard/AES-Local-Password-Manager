import SwiftUI

struct EntryDetailView: View {
    @EnvironmentObject private var store: VaultStore
    @Environment(\.dismiss) private var dismiss
    let id: UUID
    @State private var revealed: String?
    @State private var editing = false
    @State private var confirmDelete = false

    var body: some View {
        Group {
            if let entry = store.entry(id) {
                content(entry)
            } else {
                Text("This account no longer exists.").foregroundStyle(Theme.secondaryText)
            }
        }
        .themed()
        .onDisappear { revealed = nil }
    }

    private func content(_ entry: Entry) -> some View {
        List {
            Section("Username") {
                HStack {
                    Text(entry.user.isEmpty ? "—" : entry.user).textSelection(.enabled)
                    Spacer()
                    copyButton { store.copy(entry.user, label: "Username") }
                }
                .cardRow()
            }
            Section("Password") {
                HStack {
                    Text(revealed ?? "••••••••••")
                        .font(Theme.mono)
                        .textSelection(.enabled)
                    Spacer()
                    Button {
                        revealed = revealed == nil ? store.password(for: entry) : nil
                    } label: {
                        Image(systemName: revealed == nil ? "eye" : "eye.slash")
                    }
                    .buttonStyle(.borderless)
                    .accessibilityLabel(revealed == nil ? "Show password" : "Hide password")
                    copyButton { store.copy(store.password(for: entry), label: "Password") }
                }
                .cardRow()
            }
            Section("Website") {
                if let link = Self.link(entry.url) {
                    Link(entry.url, destination: link).cardRow()
                } else {
                    Text("No website").foregroundStyle(Theme.muted).cardRow()
                }
            }
            if let date = entry.createdDate {
                Section {
                    LabeledContent("Added", value: date.formatted(date: .abbreviated, time: .shortened))
                        .cardRow()
                }
            }
            Section {
                Button("Delete account", role: .destructive) { confirmDelete = true }
                    .frame(maxWidth: .infinity)
                    .cardRow()
            }
        }
        .navigationTitle(entry.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .navigationBarTrailing) {
                Button {
                    Task { await store.toggleFavourite(entry.name) }
                } label: {
                    Image(systemName: entry.favourite ? "star.fill" : "star")
                        .foregroundStyle(entry.favourite ? Theme.accent : Theme.secondaryText)
                }
                .accessibilityLabel(entry.favourite ? "Remove from favourites" : "Add to favourites")
                Button("Edit") { editing = true }
            }
        }
        .sheet(isPresented: $editing, onDismiss: { revealed = nil }) { EntryFormView(editing: entry) }
        .confirmationDialog("Delete \(entry.name)?", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("Delete", role: .destructive) {
                Task {
                    await store.delete(entry.name)
                    dismiss()
                }
            }
        }
    }

    private func copyButton(_ action: @escaping () -> Void) -> some View {
        Button(action: action) { Image(systemName: "doc.on.doc") }
            .buttonStyle(.borderless)
            .accessibilityLabel("Copy")
    }

    static func link(_ url: String) -> URL? {
        let u = url.trimmingCharacters(in: .whitespaces)
        guard !u.isEmpty else { return nil }
        return URL(string: u.contains("://") ? u : "https://" + u)
    }
}

/// Add or edit. When editing, the stored password isn't decrypted unless the
/// user asks to change it — same rule as the desktop's edit form.
struct EntryFormView: View {
    @EnvironmentObject private var store: VaultStore
    @Environment(\.dismiss) private var dismiss
    let editing: Entry?

    @State private var name = ""
    @State private var user = ""
    @State private var url = ""
    @State private var password: String?
    @State private var generating = false
    @State private var problem: String?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Account name", text: $name)
                        .textInputAutocapitalization(.words)
                    TextField("Username or email", text: $user)
                        .textContentType(.username)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }
                .cardRow()
                Section {
                    if let binding = Binding($password) {
                        RevealableField(title: "Password", text: binding)
                        Button {
                            generating = true
                        } label: {
                            Label("Generate a password", systemImage: "wand.and.stars")
                        }
                    } else {
                        HStack {
                            Text("••••••••••").foregroundStyle(Theme.secondaryText)
                            Spacer()
                            Button("Change") {
                                if let editing { password = store.password(for: editing) }
                            }
                        }
                    }
                }
                .cardRow()
                Section {
                    TextField("Website (example.com)", text: $url)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                }
                .cardRow()
                if let problem {
                    Section { Text(problem).foregroundStyle(Theme.negative) }.cardRow()
                }
            }
            .themed()
            .navigationTitle(editing == nil ? "New account" : "Edit account")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") { Task { await save() } }
                        .disabled(store.busy)
                }
            }
            .sheet(isPresented: $generating) {
                NavigationStack {
                    GeneratorView { password = $0; generating = false }
                }
            }
        }
        .onAppear {
            guard let editing else { password = ""; return }
            name = editing.name
            user = editing.user
            url = editing.url
        }
        // Don't lose a half-typed new account to a stray swipe.
        .interactiveDismissDisabled(editing == nil && !(name.isEmpty && user.isEmpty && (password ?? "").isEmpty))
    }

    private func save() async {
        let newName = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !newName.isEmpty else { problem = "Give the account a name."; return }
        let original = editing?.name
        if newName != original && store.entries.contains(where: { $0.name == newName && !$0.isDeleted }) {
            problem = VaultError.duplicate(newName).errorDescription
            return
        }
        let sealed = password.map { store.seal($0) }
        let user = self.user
        let site = url.trimmingCharacters(in: .whitespaces)
        let ok = await store.perform { entries in
            if newName != original && entries.contains(where: { $0.name == newName && !$0.isDeleted }) {
                throw VaultError.duplicate(newName)
            }
            // Reusing the name of an account deleted here: the PC still has
            // that name, so this becomes an edit of it rather than a new one.
            var reusesDeleted = false
            if newName != original, let t = entries.firstIndex(where: { $0.name == newName && $0.isDeleted }) {
                entries.remove(at: t)
                reusesDeleted = true
            }
            if let original {
                // Edited in place, so a rename keeps the entry's spot in the vault.
                guard let i = entries.firstIndex(where: { $0.name == original && !$0.isDeleted }) else {
                    throw VaultError.entryGone
                }
                if newName != original && entries[i].renamedFrom == nil && entries[i].syncState != "new" {
                    entries[i].renamedFrom = original   // the name the PC knows it by
                }
                entries[i].name = newName
                entries[i].user = user
                entries[i].url = site
                if let sealed { entries[i].sealedPassword = sealed }
                entries[i].markChanged()
                if reusesDeleted { entries[i].syncState = "changed" }
            } else {
                entries.append(Entry(name: newName, user: user, url: site, favourite: false,
                                     created: Entry.nowStamp(), sealedPassword: sealed ?? Data(),
                                     syncState: reusesDeleted ? "changed" : "new"))
            }
        }
        if ok { dismiss() }
    }
}
