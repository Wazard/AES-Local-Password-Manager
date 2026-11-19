import SwiftUI
import UniformTypeIdentifiers

struct SettingsView: View {
    @EnvironmentObject private var store: VaultStore
    @Environment(\.dismiss) private var dismiss
    @AppStorage(Prefs.lockGrace) private var lockGrace = 30
    @AppStorage(Prefs.clipboardSeconds) private var clipboardSeconds = 60
    @State private var picking = false
    @State private var receiving = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    LabeledContent("File", value: store.location?.name ?? "—")
                    LabeledContent("Stored", value: store.location?.isExternal == true ? "Opened from Files" : "On this device")
                    Button("Open a different vault…") { picking = true }
                    if store.location?.isExternal == true && VaultFiles.localVaultExists {
                        Button("Switch to the vault on this device") { store.useLocalVault() }
                    }
                } header: {
                    Text("Vault")
                } footer: {
                    Text("A vault opened from Files (for example from OneDrive) is edited in place, so the PC sees the same accounts. Switching vaults locks the app.")
                }
                .cardRow()

                Section {
                    Button { receiving = true } label: {
                        Label("Sync with PC over Wi-Fi", systemImage: "arrow.triangle.2.circlepath")
                    }
                } header: {
                    Text("Sync")
                } footer: {
                    Text(store.unsyncedCount == 0
                         ? "Everything here is already on the PC."
                         : "\(store.unsyncedCount) account(s) added, changed or deleted here since the last sync. Syncing sends them to the PC's vault and brings back what's new there.")
                }
                .cardRow()

                Section("Security") {
                    if BiometricKey.isAvailable {
                        Toggle("Unlock with \(BiometricKey.biometryName)",
                               isOn: Binding(get: { store.faceIDEnabled }, set: { store.setFaceID($0) }))
                    }
                    Picker("Lock after leaving the app", selection: $lockGrace) {
                        Text("Immediately").tag(0)
                        Text("30 seconds").tag(30)
                        Text("1 minute").tag(60)
                        Text("5 minutes").tag(300)
                    }
                    Picker("Clear copied passwords", selection: $clipboardSeconds) {
                        Text("After 30 seconds").tag(30)
                        Text("After 1 minute").tag(60)
                        Text("After 2 minutes").tag(120)
                        Text("Never").tag(0)
                    }
                    NavigationLink("Change master password") { ChangeMasterView() }
                }
                .cardRow()

                Section {
                    NavigationLink("Backups") { BackupsView() }
                } footer: {
                    Text("Every save keeps a dated copy in Files › On My iPhone › Secure Vault › backups.")
                }
                .cardRow()

                Section {
                    LabeledContent("Version", value: AppInfo.version)
                }
                .cardRow()
            }
            .themed()
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } }
            }
            .fileImporter(isPresented: $picking, allowedContentTypes: [.item]) { result in
                if case .success(let url) = result { store.adopt(url) }
            }
            .sheet(isPresented: $receiving) { ReceiveView() }
        }
    }
}

struct ChangeMasterView: View {
    @EnvironmentObject private var store: VaultStore
    @Environment(\.dismiss) private var dismiss
    @State private var current = ""
    @State private var new = ""
    @State private var confirm = ""

    var body: some View {
        let ok = !current.isEmpty && PasswordStrength.evaluate(new).ok && new == confirm
        Form {
            Section {
                RevealableField(title: "Current master password", text: $current)
            }
            .cardRow()
            Section {
                RevealableField(title: "New master password", text: $new)
                StrengthMeter(password: new).padding(.vertical, 4)
                RevealableField(title: "Confirm new password", text: $confirm)
                if !confirm.isEmpty && confirm != new {
                    Text("The passwords don't match.").font(.caption).foregroundStyle(Theme.negative)
                }
            } footer: {
                Text("The PC app keeps the old password until you lock and unlock it there.")
            }
            .cardRow()
            Section {
                Button {
                    Task {
                        if await store.changeMasterPassword(current: current, new: new) {
                            store.showToast("Master password changed")
                            dismiss()
                        }
                    }
                } label: {
                    if store.busy { ProgressView() } else { Text("Change master password") }
                }
                .disabled(!ok || store.busy)
                .frame(maxWidth: .infinity)
            }
            .cardRow()
        }
        .themed()
        .navigationTitle("Master password")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct BackupsView: View {
    @EnvironmentObject private var store: VaultStore
    @State private var backups: [BackupFile] = []
    @State private var pending: BackupFile?

    var body: some View {
        List {
            if backups.isEmpty {
                Text("No backups yet. One is made every time the vault is saved from this device.")
                    .foregroundStyle(Theme.secondaryText)
                    .cardRow()
            }
            ForEach(backups) { b in
                Button { pending = b } label: {
                    HStack {
                        Text(b.date.formatted(date: .abbreviated, time: .shortened))
                            .foregroundStyle(Theme.text)
                        Spacer()
                        Text(ByteCountFormatter.string(fromByteCount: Int64(b.size), countStyle: .file))
                            .font(.footnote)
                            .foregroundStyle(Theme.secondaryText)
                    }
                }
                .cardRow()
            }
        }
        .themed()
        .navigationTitle("Backups")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear { backups = VaultFiles.listBackups() }
        .confirmationDialog("Restore this backup?",
                            isPresented: Binding(get: { pending != nil }, set: { if !$0 { pending = nil } }),
                            titleVisibility: .visible) {
            Button("Restore") {
                if let b = pending { Task { await store.restore(b) } }
            }
        } message: {
            Text("The vault as it is now is backed up first. The app then locks — unlock with the master password the backup was saved with.")
        }
    }
}
