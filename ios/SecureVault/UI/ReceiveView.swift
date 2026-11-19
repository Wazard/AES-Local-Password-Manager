import SwiftUI

/// "Receive from PC": listens on the Wi-Fi while open, shows the code the PC
/// must type, and asks before a received vault replaces anything.
struct ReceiveView: View {
    @EnvironmentObject private var store: VaultStore
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    @StateObject private var receiver = VaultReceiver()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    switch receiver.state {
                    case .idle, .waiting: waiting
                    case .received(let vault): received(vault)
                    case .failed(let message): failed(message)
                    case .needsLocalNetwork: needsLocalNetwork
                    }
                }
                .padding(24)
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Receive from PC")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(Theme.bar, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } }
            }
        }
        .onAppear { receiver.start() }
        .onDisappear { receiver.stop() }
        // iOS suspends the app in the background, so the listener can't outlive it.
        .onChange(of: scenePhase) { phase in
            if phase == .background { receiver.stop() }
            // Back from the permission prompt or from Settings: try again by itself.
            if phase == .active && (receiver.state == .idle || receiver.state == .needsLocalNetwork) {
                receiver.start()
            }
        }
    }

    private var needsLocalNetwork: some View {
        VStack(spacing: 20) {
            Image(systemName: "wifi.exclamationmark")
                .font(.system(size: 48))
                .foregroundStyle(Theme.accent)
            Text("Allow Local Network access").font(.title3.bold())
            Text("Secure Vault needs it so your PC can find this iPhone. If iOS just asked, tap **Allow** and the app tries again by itself. Otherwise turn on **Local Network** for Secure Vault in Settings, then come back.")
                .multilineTextAlignment(.center)
                .foregroundStyle(Theme.secondaryText)
            Button("Open Settings") {
                if let url = URL(string: UIApplication.openSettingsURLString) {
                    UIApplication.shared.open(url)
                }
            }
            .buttonStyle(PrimaryButton())
            Button("Try again") { receiver.start() }
                .buttonStyle(SecondaryButton())
        }
    }

    private var waiting: some View {
        VStack(spacing: 20) {
            Image(systemName: "laptopcomputer.and.iphone")
                .font(.system(size: 48))
                .foregroundStyle(Theme.primary)
            Text("On your PC, open Secure Vault and choose **Send to iPhone**. Pick this iPhone (or type its address) and enter this code:")
                .multilineTextAlignment(.center)
                .foregroundStyle(Theme.secondaryText)
            Text(spaced(receiver.code))
                .font(.system(size: 40, weight: .semibold, design: .monospaced))
                .foregroundStyle(Theme.text)
                .padding(.vertical, 12).padding(.horizontal, 24)
                .background(Theme.card, in: RoundedRectangle(cornerRadius: 12))
                .accessibilityLabel("Code \(receiver.code.map(String.init).joined(separator: " "))")
            if let address = receiver.address {
                LabeledContent("This iPhone's address", value: address)
                    .font(.subheadline)
                    .padding(12)
                    .background(Theme.card, in: RoundedRectangle(cornerRadius: 10))
            } else {
                Text("Connect to the same Wi-Fi network as the PC.")
                    .font(.subheadline).foregroundStyle(Theme.negative)
            }
            HStack(spacing: 8) {
                ProgressView()
                Text("Waiting for the PC…").foregroundStyle(Theme.secondaryText)
            }
            Text("Keep this screen open. If the PC can't find the iPhone, check that Secure Vault is allowed under Settings › Privacy & Security › Local Network.")
                .font(.footnote)
                .foregroundStyle(Theme.muted)
                .multilineTextAlignment(.center)
        }
    }

    private func received(_ vault: ReceivedVault) -> some View {
        VStack(spacing: 20) {
            Image(systemName: "checkmark.shield.fill")
                .font(.system(size: 48))
                .foregroundStyle(Theme.positive)
            Text("Vault received from \(vault.sender)").font(.title3.bold()).multilineTextAlignment(.center)
            Text(ByteCountFormatter.string(fromByteCount: Int64(vault.data.count), countStyle: .file))
                .foregroundStyle(Theme.secondaryText)
            Text(replaceNote)
                .font(.subheadline)
                .foregroundStyle(Theme.secondaryText)
                .multilineTextAlignment(.center)
            Button("Use this vault") {
                Task {
                    await store.installReceived(vault)
                    dismiss()
                }
            }
            .buttonStyle(PrimaryButton())
            .disabled(store.busy)
            Button("Discard") {
                receiver.discard()
                dismiss()
            }
            .buttonStyle(SecondaryButton())
        }
    }

    private func failed(_ message: String) -> some View {
        VStack(spacing: 20) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 48))
                .foregroundStyle(Theme.negative)
            Text(message).multilineTextAlignment(.center)
            Button("Start again") { receiver.start() }
                .buttonStyle(PrimaryButton())
        }
    }

    private var replaceNote: String {
        var parts = ["It opens with the master password it has on the PC."]
        if VaultFiles.localVaultExists {
            parts.append("It replaces the vault stored on this iPhone, which is kept as a backup.")
        }
        if let location = store.location, location.isExternal {
            parts.append("The app will use this copy instead of \(location.name) from Files.")
        }
        return parts.joined(separator: " ")
    }

    private func spaced(_ code: String) -> String {
        guard code.count == 6 else { return code }
        return "\(code.prefix(3)) \(code.suffix(3))"
    }
}
