import SwiftUI
import UniformTypeIdentifiers

/// First run, or after "use a different vault": open an existing file or make one.
struct SetupView: View {
    @EnvironmentObject private var store: VaultStore
    @State private var picking = false
    @State private var creating = false
    @State private var receiving = false
    @State private var password = ""
    @State private var confirm = ""
    @FocusState private var focused: Bool

    var body: some View {
        ScrollView {
            VStack(spacing: 28) {
                AppHeader(subtitle: creating
                          ? "Choose a master password. It can't be recovered if you forget it."
                          : "Use the same vault as your PC, or start a new one on this device.")
                    .padding(.top, 48)

                if creating { createForm } else { choices }
            }
            .padding(24)
        }
        .scrollDismissesKeyboard(.interactively)
        .fileImporter(isPresented: $picking, allowedContentTypes: [.item]) { result in
            if case .success(let url) = result { store.adopt(url) }
        }
        .sheet(isPresented: $receiving) { ReceiveView() }
    }

    private var choices: some View {
        VStack(spacing: 12) {
            Button("Open an existing vault") { picking = true }
                .buttonStyle(PrimaryButton())
            Text("Pick **vault.pwmanager** in the Files picker — for example in your OneDrive folder. The app edits that file in place, so changes show up on the PC too.")
                .font(.footnote)
                .foregroundStyle(Theme.secondaryText)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.bottom, 8)

            Button { receiving = true } label: {
                Label("Receive from your PC over Wi-Fi", systemImage: "wifi")
            }
            .buttonStyle(SecondaryButton())

            if VaultFiles.localVaultExists {
                Button("Use the vault stored on this device") { store.useLocalVault() }
                    .buttonStyle(SecondaryButton())
            } else {
                Button("Create a new vault") { creating = true; focused = true }
                    .buttonStyle(SecondaryButton())
            }
        }
    }

    private var createForm: some View {
        let ok = PasswordStrength.evaluate(password).ok && password == confirm
        return VStack(alignment: .leading, spacing: 12) {
            RevealableField(title: "Master password", text: $password)
                .focused($focused)
                .padding(12)
                .background(Theme.input, in: RoundedRectangle(cornerRadius: 10))
            StrengthMeter(password: password)
            RevealableField(title: "Confirm master password", text: $confirm)
                .padding(12)
                .background(Theme.input, in: RoundedRectangle(cornerRadius: 10))
            if !confirm.isEmpty && confirm != password {
                Text("The passwords don't match.").font(.caption).foregroundStyle(Theme.negative)
            }
            Button {
                Task { await store.create(password: password) }
            } label: {
                if store.busy { ProgressView().tint(.white) } else { Text("Create vault") }
            }
            .buttonStyle(PrimaryButton(color: ok ? Theme.primary : Theme.muted))
            .disabled(!ok || store.busy)
            .padding(.top, 8)
            Button("Back") { creating = false; password = ""; confirm = "" }
                .frame(maxWidth: .infinity)
                .padding(.top, 4)
        }
    }
}

struct UnlockView: View {
    @EnvironmentObject private var store: VaultStore
    @State private var password = ""
    @State private var triedFaceID = false
    @State private var receiving = false
    @FocusState private var focused: Bool
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        ScrollView {
            VStack(spacing: 28) {
                AppHeader(subtitle: store.location.map {
                    $0.isExternal ? "\($0.name) · opened from Files" : "\($0.name) · on this device"
                } ?? "")
                .padding(.top, 48)

                VStack(spacing: 12) {
                    SecureField("Master password", text: $password)
                        .textContentType(.password)
                        .focused($focused)
                        .submitLabel(.go)
                        .onSubmit(unlock)
                        .padding(14)
                        .background(Theme.input, in: RoundedRectangle(cornerRadius: 10))
                        .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.border))

                    Button(action: unlock) {
                        if store.busy { ProgressView().tint(.white) } else { Text("Unlock") }
                    }
                    .buttonStyle(PrimaryButton())
                    .disabled(password.isEmpty || store.busy)

                    if store.faceIDEnabled {
                        Button {
                            Task { await store.unlockWithFaceID() }
                        } label: {
                            Label("Unlock with \(BiometricKey.biometryName)",
                                  systemImage: BiometricKey.biometryName == "Touch ID" ? "touchid" : "faceid")
                        }
                        .buttonStyle(SecondaryButton())
                        .disabled(store.busy)
                    }
                }

                HStack(spacing: 20) {
                    Button("Use a different vault") { store.chooseAnotherVault() }
                    Button("Receive from PC") { receiving = true }
                }
                .font(.footnote)
                Text("v\(AppInfo.version)").font(.caption2).foregroundStyle(Theme.muted)
            }
            .padding(24)
        }
        .scrollDismissesKeyboard(.interactively)
        .sheet(isPresented: $receiving) { ReceiveView() }
        .onAppear { offerFaceID() }
        .onChange(of: scenePhase) { if $0 == .active { offerFaceID() } }
    }

    /// Face ID straight away, once per lock screen — but only with the app in
    /// front (the screen can appear while it is still in the background).
    private func offerFaceID() {
        guard scenePhase == .active else { return }
        guard store.faceIDEnabled, !triedFaceID else { focused = true; return }
        triedFaceID = true
        Task { await store.unlockWithFaceID() }
    }

    private func unlock() {
        guard !password.isEmpty, !store.busy else { return }
        let typed = password
        password = ""
        Task { await store.unlock(password: typed) }
    }
}
