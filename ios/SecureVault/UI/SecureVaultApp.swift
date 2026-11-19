import SwiftUI

@main
struct SecureVaultApp: App {
    @StateObject private var store = VaultStore()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(store)
                .preferredColorScheme(.dark)
                .tint(Theme.primary)
                // Hide the vault from the app-switcher snapshot.
                .overlay {
                    if scenePhase != .active && store.phase == .unlocked { PrivacyCover() }
                }
        }
        .onChange(of: scenePhase) { store.scenePhaseChanged($0) }
    }
}

struct RootView: View {
    @EnvironmentObject private var store: VaultStore

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            switch store.phase {
            case .setup: SetupView()
            case .locked: UnlockView()
            case .unlocked: VaultListView()
            }
        }
        .foregroundStyle(Theme.text)
        .overlay(alignment: .bottom) {
            if let toast = store.toast {
                Text(toast)
                    .font(.subheadline.weight(.medium))
                    .padding(.horizontal, 16).padding(.vertical, 10)
                    .background(Theme.card, in: Capsule())
                    .overlay(Capsule().stroke(Theme.border))
                    .padding(.bottom, 24)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .animation(.easeOut(duration: 0.2), value: store.toast)
        .alert("Secure Vault", isPresented: Binding(get: { store.error != nil },
                                                   set: { if !$0 { store.error = nil } })) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(store.error ?? "")
        }
    }
}

struct PrivacyCover: View {
    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            Image(systemName: "lock.shield.fill")
                .font(.system(size: 64))
                .foregroundStyle(Theme.primary)
        }
    }
}

struct AppHeader: View {
    let subtitle: String

    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: "lock.shield.fill")
                .font(.system(size: 56))
                .foregroundStyle(Theme.primary)
            Text("Secure Vault").font(.largeTitle.bold())
            Text(subtitle)
                .font(.subheadline)
                .foregroundStyle(Theme.secondaryText)
                .multilineTextAlignment(.center)
        }
    }
}

enum AppInfo {
    static var version: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "?"
    }
}
