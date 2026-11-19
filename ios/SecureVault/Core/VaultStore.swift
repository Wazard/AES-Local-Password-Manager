import SwiftUI
import UIKit
import CryptoKit

enum SortMode: String, CaseIterable, Identifiable {
    // Same identifiers as the desktop's sort modes.
    case nameAsc = "name_asc", nameDesc = "name_desc", timeNew = "time_new", timeOld = "time_old"
    var id: String { rawValue }
    var label: String {
        switch self {
        case .nameAsc: return "Name (A–Z)"
        case .nameDesc: return "Name (Z–A)"
        case .timeNew: return "Newest first"
        case .timeOld: return "Oldest first"
        }
    }
}

enum Prefs {
    static let lockGrace = "lockGraceSeconds"
    static let clipboardSeconds = "clipboardSeconds"
    static let faceID = "faceIDEnabled"
    static let sort = "sortMode"
}

@MainActor
final class VaultStore: ObservableObject {
    enum Phase { case setup, locked, unlocked }

    @Published private(set) var phase: Phase
    @Published private(set) var location: VaultLocation?
    @Published private(set) var entries: [Entry] = []
    @Published private(set) var busy = false
    @Published var error: String?
    @Published var toast: String?

    private var key: VaultKey?
    private var session = SessionCrypto()
    /// Hash of the file as we last read or wrote it — how a save notices that
    /// another device (the PC, through OneDrive) saved in the meantime.
    private var lastHash: Data?
    private var backgroundedAt: Date?

    init() {
        UserDefaults.standard.register(defaults: [Prefs.lockGrace: 30, Prefs.clipboardSeconds: 60])
        let found = VaultFiles.current()
        location = found
        phase = found == nil ? .setup : .locked
    }

    var faceIDEnabled: Bool { UserDefaults.standard.bool(forKey: Prefs.faceID) }

    // MARK: - Choosing a vault

    func adopt(_ url: URL) {
        do {
            let found = try VaultFiles.adopt(url)
            switchTo(found)
        } catch {
            report(error)
        }
    }

    func useLocalVault() {
        VaultFiles.forgetExternal()
        switchTo(VaultFiles.localVaultExists ? VaultLocation(url: VaultFiles.localVault, isExternal: false) : nil)
    }

    func chooseAnotherVault() {
        lock()
        phase = .setup
    }

    private func switchTo(_ newLocation: VaultLocation?) {
        lock()
        if newLocation != location { disableFaceID() }
        location = newLocation
        phase = newLocation == nil ? .setup : .locked
    }

    // MARK: - Unlocking

    func create(password: String) async {
        guard !VaultFiles.localVaultExists else { return report(VaultError.alreadyExists) }
        await working {
            let key = try await Task.detached { try VaultFormat.newKey(password) }.value
            let target = VaultLocation(url: VaultFiles.localVault, isExternal: false)
            let s = SessionCrypto()
            let blob = try Self.seal([], session: s, key: key)
            try await Task.detached { try VaultFiles.write(blob, to: target) }.value
            VaultFiles.makeBackup(blob)
            VaultFiles.forgetExternal()
            disableFaceID()
            location = target
            session = s
            entries = []
            self.key = key
            lastHash = Self.hash(blob)
            phase = .unlocked
        }
    }

    func unlock(password: String) async {
        guard let location else { return }
        await working {
            let (blob, opened) = try await Task.detached {
                let blob = try VaultFiles.read(location)
                return (blob, try VaultFormat.open(blob, password: password))
            }.value
            try load(payload: opened.payload, blob: blob, key: opened.key)
            // Keep the stored Face ID key in step with the master password.
            if faceIDEnabled { try? BiometricKey.save(opened.key) }
            phase = .unlocked
        }
    }

    func unlockWithFaceID() async {
        guard let location, faceIDEnabled else { return }
        await working {
            let key: VaultKey
            do {
                guard let stored = try await Task.detached(operation: { try BiometricKey.load() }).value
                else { return }
                key = stored
            } catch {
                disableFaceID()
                throw error
            }
            let blob = try await Task.detached { try VaultFiles.read(location) }.value
            let payload: Data
            do {
                payload = try VaultFormat.open(blob, key: key)
            } catch VaultError.changedElsewhere {
                disableFaceID()
                throw VaultError.faceIDOutdated
            }
            try load(payload: payload, blob: blob, key: key)
            phase = .unlocked
        }
    }

    private func load(payload: Data, blob: Data, key: VaultKey) throws {
        let s = SessionCrypto()
        let loaded = try VaultCodec.decode(try Gzip.decompress(payload), session: s)
        session = s
        entries = loaded
        self.key = key
        lastHash = Self.hash(blob)
    }

    func lock() {
        entries = []
        key = nil
        session = SessionCrypto()
        lastHash = nil
        if phase == .unlocked { phase = .locked }
    }

    func scenePhaseChanged(_ scene: ScenePhase) {
        let grace = TimeInterval(UserDefaults.standard.integer(forKey: Prefs.lockGrace))
        switch scene {
        case .background:
            if grace == 0 { lock() } else if backgroundedAt == nil { backgroundedAt = Date() }
        case .active:
            if let t = backgroundedAt, Date().timeIntervalSince(t) >= grace { lock() }
            backgroundedAt = nil
        default:
            break
        }
    }

    // MARK: - Passwords

    func password(for entry: Entry) -> String { session.open(entry.sealedPassword) }
    func seal(_ password: String) -> Data { session.seal(password) }

    func copy(_ text: String, label: String) {
        let seconds = UserDefaults.standard.integer(forKey: Prefs.clipboardSeconds)
        var options: [UIPasteboard.OptionsKey: Any] = [.localOnly: true]
        if seconds > 0 { options[.expirationDate] = Date().addingTimeInterval(TimeInterval(seconds)) }
        UIPasteboard.general.setItems([["public.utf8-plain-text": text]], options: options)
        showToast("\(label) copied")
    }

    func showToast(_ message: String) {
        toast = message
        Task {
            try? await Task.sleep(nanoseconds: 1_600_000_000)
            if toast == message { toast = nil }
        }
    }

    // MARK: - Editing

    /// Every edit goes through here. The change is applied to the vault as it
    /// is on disk *now*: if another device saved since we loaded, its version
    /// is picked up first, so its edits are kept instead of overwritten.
    /// Changes must therefore find entries by name, not by `id`.
    @discardableResult
    func perform(_ change: (inout [Entry]) throws -> Void) async -> Bool {
        do {
            try await commit(rekey: nil, change)
            return true
        } catch {
            report(error)
            return false
        }
    }

    private func commit(rekey: VaultKey?, _ change: (inout [Entry]) throws -> Void) async throws {
        guard let key, let location else { throw VaultError.locked }
        let current = try await Task.detached { try VaultFiles.read(location) }.value
        var working = entries
        if Self.hash(current) != lastHash {
            let fresh = try VaultCodec.decode(try Gzip.decompress(try VaultFormat.open(current, key: key)),
                                              session: session)
            // Keep ids stable for entries that are still there, so open screens stay put.
            let ids = Dictionary(entries.map { ($0.name, $0.id) }, uniquingKeysWith: { a, _ in a })
            working = fresh.map { e in var e = e; e.id = ids[e.name] ?? e.id; return e }
        }
        try change(&working)
        let saveKey = rekey ?? key
        let blob = try Self.seal(working, session: session, key: saveKey)
        try await Task.detached { try VaultFiles.write(blob, to: location) }.value
        entries = working
        self.key = saveKey
        lastHash = Self.hash(blob)
        VaultFiles.makeBackup(blob)
    }

    func toggleFavourite(_ name: String) async {
        await perform { entries in
            guard let i = entries.firstIndex(where: { $0.name == name }) else { throw VaultError.entryGone }
            entries[i].favourite.toggle()
            entries[i].markChanged()
        }
    }

    /// In a vault kept on this iPhone, an account the PC may have is only
    /// marked deleted, so the next sync deletes it there too; it disappears
    /// for good when the PC sends the merged vault back. One created here and
    /// never synced, or one in a vault opened from Files (the PC's own file),
    /// is simply removed.
    func delete(_ name: String) async {
        let keepTombstone = location?.isExternal == false
        await perform { entries in
            guard let i = entries.firstIndex(where: { $0.name == name }) else { return }
            if keepTombstone && entries[i].syncState != "new" {
                entries[i].syncState = "deleted"
            } else {
                entries.remove(at: i)
            }
        }
    }

    /// Accounts changed here since the last sync with the PC.
    var unsyncedCount: Int { entries.filter { $0.syncState != nil }.count }

    /// After a sync the file holds the merged vault: show it (same key, as
    /// the PC opened the phone's copy with its own). Locks if that fails.
    func reloadAfterSync() async {
        guard phase == .unlocked, let key, let location else { return }
        do {
            let blob = try await Task.detached { try VaultFiles.read(location) }.value
            try load(payload: try VaultFormat.open(blob, key: key), blob: blob, key: key)
        } catch {
            lock()
        }
    }

    func changeMasterPassword(current: String, new: String) async -> Bool {
        guard let key else { return false }
        var ok = false
        await working {
            let matches = await Task.detached { VaultFormat.matches(current, key) }.value
            guard matches else { throw VaultError.wrongPassword }
            let newKey = try await Task.detached { try VaultFormat.newKey(new) }.value
            try await commit(rekey: newKey) { _ in }
            if faceIDEnabled { try? BiometricKey.save(newKey) }
            ok = true
        }
        return ok
    }

    // MARK: - Settings

    func setFaceID(_ on: Bool) {
        if on, let key {
            do {
                try BiometricKey.save(key)
                UserDefaults.standard.set(true, forKey: Prefs.faceID)
            } catch {
                report(error)
            }
        } else {
            disableFaceID()
        }
        objectWillChange.send()
    }

    private func disableFaceID() {
        BiometricKey.clear()
        UserDefaults.standard.set(false, forKey: Prefs.faceID)
    }

    /// Puts a backup back as the live vault, then locks: the restored copy may
    /// have a different master password. The current state is backed up first,
    /// so restoring the wrong one can be undone.
    func restore(_ backup: BackupFile) async {
        guard let location else { return }
        await working {
            let blob = try VaultFiles.readBackup(backup)
            let current = try? await Task.detached { try VaultFiles.read(location) }.value
            if let current { VaultFiles.makeBackup(current) }
            try await Task.detached { try VaultFiles.write(blob, to: location) }.value
            lock()
            showToast("Backup restored")
        }
    }

    /// Makes a vault sent from the PC the one this app uses: it is written to
    /// the app's own folder (the vault already there is backed up first) and
    /// the app switches to it, locked, ready for that vault's master password.
    func installReceived(_ received: ReceivedVault) async {
        await working {
            let target = VaultLocation(url: VaultFiles.localVault, isExternal: false)
            if VaultFiles.localVaultExists, let current = try? Data(contentsOf: VaultFiles.localVault) {
                VaultFiles.makeBackup(current)
            }
            try await Task.detached { try VaultFiles.write(received.data, to: target) }.value
            VaultFiles.forgetExternal()
            lock()
            disableFaceID()
            location = target
            phase = .locked
            showToast("Vault received from \(received.sender)")
        }
    }

    // MARK: - Helpers

    private func working(_ body: () async throws -> Void) async {
        busy = true
        defer { busy = false }
        do { try await body() } catch { report(error) }
    }

    private func report(_ error: Error) {
        self.error = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
    }

    private static func seal(_ entries: [Entry], session: SessionCrypto, key: VaultKey) throws -> Data {
        try VaultFormat.seal(try Gzip.compress(VaultCodec.encode(entries, session: session)), with: key)
    }

    private static func hash(_ data: Data) -> Data { Data(SHA256.hash(data: data)) }

    func visible(query: String, sort: SortMode) -> [Entry] {
        Search.visible(entries, query: query, sort: sort)
    }

    func entry(_ id: UUID) -> Entry? { entries.first { $0.id == id && !$0.isDeleted } }
}
