import Foundation

/// Where the vault lives: a file this app made in its own Documents folder
/// (visible in Files › On My iPhone › Secure Vault), or one the user picked
/// elsewhere — the desktop's vault in OneDrive, say — opened in place through a
/// security-scoped bookmark, so the phone and the PC edit the same file.
struct VaultLocation: Equatable {
    let url: URL
    let isExternal: Bool
    var name: String { url.lastPathComponent }
}

struct BackupFile: Identifiable {
    let url: URL
    let date: Date
    let size: Int
    var id: URL { url }
}

enum VaultFiles {
    static let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    static let localVault = documents.appendingPathComponent("vault.pwmanager")
    static let backupsDir = documents.appendingPathComponent("backups", isDirectory: true)
    private static let bookmarkKey = "externalVaultBookmark"

    static var localVaultExists: Bool { FileManager.default.fileExists(atPath: localVault.path) }

    /// The vault the app was last pointed at, if it can still be found.
    static func current() -> VaultLocation? {
        if let data = UserDefaults.standard.data(forKey: bookmarkKey) {
            var stale = false
            guard let url = try? URL(resolvingBookmarkData: data, bookmarkDataIsStale: &stale) else {
                forgetExternal()
                return nil
            }
            if stale { try? remember(url) }
            return VaultLocation(url: url, isExternal: true)
        }
        return localVaultExists ? VaultLocation(url: localVault, isExternal: false) : nil
    }

    /// Points the app at a file picked in the Files picker.
    static func adopt(_ url: URL) throws -> VaultLocation {
        guard looksLikeVault(url) else { throw VaultError.notAVault }
        if url.resolvingSymlinksInPath() == localVault.resolvingSymlinksInPath() {
            forgetExternal()
            return VaultLocation(url: localVault, isExternal: false)
        }
        try remember(url)
        return VaultLocation(url: url, isExternal: true)
    }

    static func looksLikeVault(_ url: URL) -> Bool {
        guard let blob = try? coordinatedRead(url) else { return false }
        return VaultFormat.looksLikeVault(blob)
    }

    static func forgetExternal() {
        UserDefaults.standard.removeObject(forKey: bookmarkKey)
    }

    private static func remember(_ url: URL) throws {
        try withAccess(url) {
            let data = try url.bookmarkData(options: [], includingResourceValuesForKeys: nil, relativeTo: nil)
            UserDefaults.standard.set(data, forKey: bookmarkKey)
        }
    }

    // MARK: - Reading and writing

    static func read(_ location: VaultLocation) throws -> Data {
        try coordinatedRead(location.url)
    }

    static func write(_ data: Data, to location: VaultLocation) throws {
        // A file in another app's storage (OneDrive, iCloud Drive) is written
        // in place: the picker grants access to that one file, not to its
        // folder, so write-to-temp-then-rename isn't possible there. Every
        // saved state is also kept as a backup, which covers a torn write.
        let options: Data.WritingOptions = location.isExternal ? [] : [.atomic, .completeFileProtection]
        try withAccess(location.url) {
            var coordError: NSError?
            var writeError: Error?
            NSFileCoordinator().coordinate(writingItemAt: location.url, options: .forReplacing,
                                           error: &coordError) { url in
                do { try data.write(to: url, options: options) } catch { writeError = error }
            }
            if let e = coordError ?? writeError { throw VaultError.unreadable(e.localizedDescription) }
        }
    }

    /// A coordinated read also makes a cloud provider download the latest copy.
    private static func coordinatedRead(_ url: URL) throws -> Data {
        try withAccess(url) {
            var coordError: NSError?
            var result: Result<Data, Error> = .failure(VaultError.notAVault)
            NSFileCoordinator().coordinate(readingItemAt: url, options: [], error: &coordError) { url in
                result = Result { try Data(contentsOf: url) }
            }
            if let e = coordError { throw VaultError.unreadable(e.localizedDescription) }
            do { return try result.get() } catch { throw VaultError.unreadable(error.localizedDescription) }
        }
    }

    private static func withAccess<T>(_ url: URL, _ body: () throws -> T) rethrows -> T {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        return try body()
    }

    // MARK: - Backups (same naming and retention as core/backup.py)

    private static let keepRecent = 20
    private static let keepDays = 60.0

    private static let stamp: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy_MM_dd_HHmm"
        return f
    }()

    /// A dated copy of a saved state: vault_bk_2026_08_08_1432_01.pwmanager.
    /// Never throws — a failed backup must not turn a good save into a bad one.
    static func makeBackup(_ blob: Data) {
        let fm = FileManager.default
        try? fm.createDirectory(at: backupsDir, withIntermediateDirectories: true)
        let base = "vault_bk_" + stamp.string(from: Date()) + "_"
        for index in 1...99 {
            let url = backupsDir.appendingPathComponent(base + String(format: "%02d", index) + ".pwmanager")
            if !fm.fileExists(atPath: url.path) {
                try? blob.write(to: url, options: [.atomic, .completeFileProtection])
                break
            }
        }
        prune()
    }

    /// Newest first (the names sort chronologically).
    static func listBackups() -> [BackupFile] {
        let names = (try? FileManager.default.contentsOfDirectory(atPath: backupsDir.path)) ?? []
        return names.sorted(by: >).compactMap { name -> BackupFile? in
            guard name.hasPrefix("vault_bk_"), name.hasSuffix(".pwmanager"), name.count == 37,
                  let date = stamp.date(from: String(name.dropFirst(9).prefix(15)))
            else { return nil }
            let url = backupsDir.appendingPathComponent(name)
            let attributes = try? FileManager.default.attributesOfItem(atPath: url.path)
            return BackupFile(url: url, date: date, size: attributes?[.size] as? Int ?? 0)
        }
    }

    static func readBackup(_ backup: BackupFile) throws -> Data {
        let blob = try Data(contentsOf: backup.url)
        guard VaultFormat.looksLikeVault(blob) else { throw VaultError.notAVault }
        return blob
    }

    /// Keep the newest `keepRecent`, plus the last backup of each day within `keepDays`.
    private static func prune() {
        let backups = listBackups()
        var keep = Set(backups.prefix(keepRecent).map(\.url))
        let cutoff = Date().addingTimeInterval(-keepDays * 86400)
        var days = Set<DateComponents>()
        for b in backups where b.date >= cutoff {
            if days.insert(Calendar.current.dateComponents([.year, .month, .day], from: b.date)).inserted {
                keep.insert(b.url)
            }
        }
        for b in backups where !keep.contains(b.url) {
            try? FileManager.default.removeItem(at: b.url)
        }
    }
}
