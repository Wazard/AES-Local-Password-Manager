import SwiftUI

/// "Connect to PC": listens on the Wi-Fi while open and shows the code the PC
/// must type. The PC either syncs (this vault goes to the PC, the merged one
/// comes back) or replaces this vault, which asks here first.
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
                    case .synced(let sender): synced(sender)
                    case .failed(let message): failed(message)
                    case .needsLocalNetwork: needsLocalNetwork
                    }
                }
                .padding(24)
            }
            .background(Theme.background.ignoresSafeArea())
            .navigationTitle("Connect to PC")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(Theme.bar, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } }
            }
        }
        .onAppear { receiver.start(location: store.location) }
        .onDisappear { receiver.stop() }
        // iOS suspends the app in the background, so the listener can't outlive it.
        .onChange(of: scenePhase) { phase in
            if phase == .background { receiver.stop() }
            // Back from the permission prompt or from Settings: try again by itself.
            if phase == .active && (receiver.state == .idle || receiver.state == .needsLocalNetwork) {
                receiver.start(location: store.location)
            }
        }
        .onChange(of: receiver.state) { state in
            // Show the merged vault straight away if it is open here.
            if case .synced = state { Task { await store.reloadAfterSync() } }
        }
    }

    private var needsLocalNetwork: some View {
        VStack(spacing: 20) {
            Image(systemName: "wifi.exclamationmark")
                .font(.system(size: 48))
                .foregroundStyle(Theme.accent)
            Text("Allow Local Network access").font(.title3.bold())
            Text("Secure Vault needs it so your PC can find this iPhone. If iOS just asked, tap **Allow** and the app tries again by itself. Otherwise turn on **Local Network** for Secure Vault in Settings — or for LiveContainer, if the app runs inside it — then come back.")
                .multilineTextAlignment(.center)
                .foregroundStyle(Theme.secondaryText)
            Button("Open Settings") {
                if let url = URL(string: UIApplication.openSettingsURLString) {
                    UIApplication.shared.open(url)
                }
            }
            .buttonStyle(PrimaryButton())
            Button("Try again") { receiver.start(location: store.location) }
                .buttonStyle(SecondaryButton())
        }
    }

    private var waiting: some View {
        VStack(spacing: 20) {
            Image(systemName: "laptopcomputer.and.iphone")
                .font(.system(size: 48))
                .foregroundStyle(Theme.primary)
            Text("On your PC, open Secure Vault, click the phone icon and choose **Sync**. Pick this iPhone (or type its address) and enter this code:")
                .multilineTextAlignment(.center)
                .foregroundStyle(Theme.secondaryText)
            Text(spaced(receiver.code))
                .font(.system(size: 40, weight: .semibold, design: .monospaced))
                .foregroundStyle(Theme.text)
                .padding(.vertical, 12).padding(.horizontal, 24)
                .background(Theme.card, in: RoundedRectangle(cornerRadius: 12))
                .accessibilityLabel("Code \(receiver.code.map(String.init).joined(separator: " "))")
            if let address = receiver.address {
                VStack(spacing: 8) {
                    LabeledContent("This iPhone's address", value: address)
                        .font(receiver.announced ? .subheadline : .headline)
                    if !receiver.announced {
                        // Typical inside LiveContainer: iOS won't let the app announce itself,
                        // so the PC only finds it by probing the network.
                        Text("iOS won't let this iPhone announce itself here. The PC should still find it by its address; if it doesn't, type this address on the PC.")
                            .font(.footnote)
                            .foregroundStyle(Theme.accent)
                            .multilineTextAlignment(.center)
                    }
                }
                .padding(12)
                .background(Theme.card, in: RoundedRectangle(cornerRadius: 10))
                .overlay(RoundedRectangle(cornerRadius: 10)
                    .stroke(receiver.announced ? Color.clear : Theme.accent))
            } else {
                Text("Connect to the same Wi-Fi network as the PC.")
                    .font(.subheadline).foregroundStyle(Theme.negative)
            }
            HStack(spacing: 8) {
                ProgressView()
                Text("Waiting for the PC…").foregroundStyle(Theme.secondaryText)
            }
            Text("Keep this screen open. If sending fails, check under Settings › Privacy & Security › Local Network that the app is allowed — inside LiveContainer the switch is LiveContainer's.")
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

    private func synced(_ sender: String) -> some View {
        VStack(spacing: 20) {
            Image(systemName: "arrow.triangle.2.circlepath.circle.fill")
                .font(.system(size: 48))
                .foregroundStyle(Theme.positive)
            Text("Synced with \(sender)").font(.title3.bold()).multilineTextAlignment(.center)
            Text("Your changes are in the PC's vault, and this iPhone now has the same vault as the PC. The previous version is kept in the backups.")
                .font(.subheadline)
                .foregroundStyle(Theme.secondaryText)
                .multilineTextAlignment(.center)
            Button("Done") { dismiss() }
                .buttonStyle(PrimaryButton())
        }
    }

    private func failed(_ message: String) -> some View {
        VStack(spacing: 20) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 48))
                .foregroundStyle(Theme.negative)
            Text(message).multilineTextAlignment(.center)
            Button("Start again") { receiver.start(location: store.location) }
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
