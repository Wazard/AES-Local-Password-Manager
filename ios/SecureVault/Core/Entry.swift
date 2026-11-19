import Foundation
import CryptoKit

/// One account. The password is never kept as plaintext: it is sealed with a
/// key made fresh at every unlock and opened only when it is shown, copied or
/// saved — the same idea as the desktop's `SessionCrypto`.
struct Entry: Identifiable {
    /// Stable for this unlock only; the name is the real key in the file.
    var id = UUID()
    var name: String
    var user: String
    var url: String
    var favourite: Bool
    /// As stored: a float on new entries, an int on some, absent on legacy ones.
    var created: JSONValue?
    var sealedPassword: Data
    /// Keys this version doesn't know about, written back untouched.
    var extra: [(String, JSONValue)] = []
    /// Not yet synced to the PC: "new", "changed" or "deleted" (see
    /// data_handler.merge_phone_changes). Stored in the vault as "sync_pending".
    var syncState: String?
    /// The name the PC knows this entry by, if it was renamed here.
    var renamedFrom: String?

    /// Deleted here but kept until the PC has heard about it.
    var isDeleted: Bool { syncState == "deleted" }

    /// Record a change for the next sync. Something created here and never
    /// synced stays "new" whatever happens to it afterwards.
    mutating func markChanged() {
        if syncState != "new" { syncState = "changed" }
    }

    var createdDate: Date? {
        if case .number(let n)? = created, let t = Double(n) { return Date(timeIntervalSince1970: t) }
        return nil
    }

    static func nowStamp() -> JSONValue {
        .number(String(format: "%.6f", Date().timeIntervalSince1970))
    }
}

final class SessionCrypto {
    private let key = SymmetricKey(size: .bits256)

    func seal(_ plaintext: String) -> Data {
        (try? AES.GCM.seal(Data(plaintext.utf8), using: key).combined) ?? Data()
    }

    func open(_ sealed: Data) -> String {
        guard !sealed.isEmpty,
              let box = try? AES.GCM.SealedBox(combined: sealed),
              let plain = try? AES.GCM.open(box, using: key)
        else { return "" }
        return String(decoding: plain, as: UTF8.self)
    }
}

/// JSON payload <-> entries, in file order.
enum VaultCodec {
    private static let known: Set<String> = ["user", "pass", "url", "created", "favourite",
                                             "sync_pending", "sync_renamed_from"]

    static func decode(_ json: Data, session: SessionCrypto) throws -> [Entry] {
        guard case .object(let services) = try JSON.parse(json) else { throw VaultError.damaged }
        return services.map { name, value -> Entry in
            var fields: [(String, JSONValue)] = []
            if case .object(let f) = value { fields = f }
            func field(_ key: String) -> JSONValue? { fields.first { $0.0 == key }?.1 }
            var syncState = field("sync_pending")?.stringValue
            if syncState == nil, field("sync_pending")?.boolValue == true { syncState = "changed" }
            return Entry(
                name: name,
                user: field("user")?.stringValue ?? "",
                url: field("url")?.stringValue ?? "",
                favourite: field("favourite")?.boolValue ?? false,
                created: field("created"),
                sealedPassword: session.seal(field("pass")?.stringValue ?? ""),
                extra: fields.filter { !known.contains($0.0) },
                syncState: syncState,
                renamedFrom: field("sync_renamed_from")?.stringValue)
        }
    }

    /// The plaintext exists only inside the returned bytes, which the caller
    /// compresses and encrypts straight away.
    static func encode(_ entries: [Entry], session: SessionCrypto) -> Data {
        let services: [(String, JSONValue)] = entries.map { e in
            var fields: [(String, JSONValue)] = [
                ("user", .string(e.user)),
                ("pass", .string(session.open(e.sealedPassword))),
                ("url", .string(e.url)),
            ]
            if let created = e.created { fields.append(("created", created)) }
            fields.append(("favourite", .bool(e.favourite)))
            if let state = e.syncState { fields.append(("sync_pending", .string(state))) }
            if let old = e.renamedFrom { fields.append(("sync_renamed_from", .string(old))) }
            return (e.name, .object(fields + e.extra))
        }
        return JSON.serialize(.object(services))
    }
}
