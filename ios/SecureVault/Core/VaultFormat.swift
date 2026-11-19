import Foundation
import CryptoKit
import CommonCrypto

/// The `.pwmanager` file format, byte for byte the same as the desktop app's
/// `core/encryption.py`, so one vault file works on both.
///
///     v2: "PWV2" | time(1) | memory KiB(4, big-endian) | lanes(1) | salt(16)
///              | nonce(12) | AES-256-GCM ciphertext + tag
///     v1 (legacy): salt(16) | nonce(12) | ciphertext + tag, PBKDF2-SHA256
///
/// The plaintext is gzip-compressed JSON: { service: {user, pass, url, ...} }.

struct KDFParams: Equatable {
    var time: UInt8
    var memoryKiB: UInt32
    var parallelism: UInt8

    /// Argon2id defaults, same as the desktop: 64 MiB, 3 passes, 4 lanes.
    static let standard = KDFParams(time: 3, memoryKiB: 64 * 1024, parallelism: 4)
}

/// What a save needs: the key derived at unlock, plus the salt and parameters
/// it came from (they go into every file header). The master password itself
/// is discarded once this exists.
struct VaultKey {
    let key: SymmetricKey
    let salt: Data
    let params: KDFParams
}

enum VaultError: LocalizedError {
    case wrongPassword
    case notAVault
    case damaged
    case keyFailed
    case changedElsewhere
    case faceIDOutdated
    case locked
    case duplicate(String)
    case entryGone
    case alreadyExists
    case unreadable(String)

    var errorDescription: String? {
        switch self {
        case .wrongPassword: return "Wrong master password."
        case .notAVault: return "That file doesn't look like a Secure Vault file."
        case .damaged: return "The vault file is damaged and can't be read."
        case .keyFailed: return "Couldn't derive the vault key."
        case .changedElsewhere:
            return "The vault was changed on another device with a different master password. Lock the app and unlock it with the new password. Your last change was not saved."
        case .faceIDOutdated:
            return "Face ID unlock needs setting up again — the master password or the enrolled faces changed. Unlock with your password, then turn it back on in Settings."
        case .locked: return "The vault is locked."
        case .duplicate(let name): return "An account named “\(name)” already exists."
        case .entryGone: return "That account no longer exists — it may have been deleted on another device."
        case .alreadyExists: return "A vault already exists in this app. Open it instead."
        case .unreadable(let why): return "Couldn't read the vault: \(why)"
        }
    }
}

enum VaultFormat {
    static let magic = Data("PWV2".utf8)
    static let headerLength = 4 + 1 + 4 + 1 + 16
    private static let legacyIterations: UInt32 = 100_000

    struct Opened {
        let payload: Data
        /// The key future saves use. For a legacy file it is fresh Argon2id
        /// material, so the next save migrates the file, like the desktop does.
        let key: VaultKey
        let migrated: Bool
    }

    /// The same cheap check the desktop does before adopting a picked file.
    static func looksLikeVault(_ blob: Data) -> Bool {
        blob.prefix(4) == magic || blob.count > 28
    }

    static func open(_ blob: Data, password: String) throws -> Opened {
        let b = [UInt8](blob)
        if let header = parseHeader(b) {
            let key = try argon2id(password, salt: header.salt, params: header.params)
            let payload = try decrypt(Data(b[headerLength...]), with: key)
            return Opened(payload: payload,
                          key: VaultKey(key: key, salt: header.salt, params: header.params),
                          migrated: false)
        }
        guard b.count > 28 + 16 else { throw VaultError.notAVault }
        let legacyKey = try pbkdf2(password, salt: Data(b[0..<16]))
        let payload = try decrypt(Data(b[16...]), with: legacyKey)
        return Opened(payload: payload, key: try newKey(password), migrated: true)
    }

    /// Opens a v2 file with a key already in hand (Face ID unlock, or picking
    /// up a save made on another device). Fails if the file was re-keyed.
    static func open(_ blob: Data, key: VaultKey) throws -> Data {
        let b = [UInt8](blob)
        guard let header = parseHeader(b), header.salt == key.salt, header.params == key.params else {
            throw VaultError.changedElsewhere
        }
        return try decrypt(Data(b[headerLength...]), with: key.key)
    }

    static func seal(_ payload: Data, with key: VaultKey) throws -> Data {
        guard let combined = try AES.GCM.seal(payload, using: key.key).combined else {
            throw VaultError.keyFailed
        }
        var out = magic
        out.append(key.params.time)
        withUnsafeBytes(of: key.params.memoryKiB.bigEndian) { out.append(contentsOf: $0) }
        out.append(key.params.parallelism)
        out.append(key.salt)
        out.append(combined)   // nonce | ciphertext | tag — the same order Python's AESGCM uses
        return out
    }

    /// A fresh salt and the standard parameters (new vault, or a new master password).
    static func newKey(_ password: String) throws -> VaultKey {
        let salt = SymmetricKey(size: SymmetricKeySize(bitCount: 128)).withUnsafeBytes { Data($0) }
        let params = KDFParams.standard
        return VaultKey(key: try argon2id(password, salt: salt, params: params), salt: salt, params: params)
    }

    /// Re-derives a key to check a password against the vault's own salt.
    static func matches(_ password: String, _ key: VaultKey) -> Bool {
        guard let derived = try? argon2id(password, salt: key.salt, params: key.params) else { return false }
        let a = derived.withUnsafeBytes { Data($0) }
        let b = key.key.withUnsafeBytes { Data($0) }
        return a == b
    }

    // MARK: - Pieces

    private static func parseHeader(_ b: [UInt8]) -> (salt: Data, params: KDFParams)? {
        guard b.count >= headerLength + 12 + 16, Data(b[0..<4]) == magic else { return nil }
        let memory = UInt32(b[5]) << 24 | UInt32(b[6]) << 16 | UInt32(b[7]) << 8 | UInt32(b[8])
        return (Data(b[10..<26]), KDFParams(time: b[4], memoryKiB: memory, parallelism: b[9]))
    }

    private static func decrypt(_ combined: Data, with key: SymmetricKey) throws -> Data {
        do {
            return try AES.GCM.open(AES.GCM.SealedBox(combined: combined), using: key)
        } catch {
            throw VaultError.wrongPassword
        }
    }

    static func argon2id(_ password: String, salt: Data, params: KDFParams) throws -> SymmetricKey {
        var out = [UInt8](repeating: 0, count: 32)
        defer { out.withUnsafeMutableBytes { _ = memset_s($0.baseAddress, $0.count, 0, $0.count) } }
        let pwd = Array(password.utf8)
        let rc = pwd.withUnsafeBytes { p in
            salt.withUnsafeBytes { s in
                argon2id_hash_raw(UInt32(params.time), params.memoryKiB, UInt32(params.parallelism),
                                  p.baseAddress, p.count, s.baseAddress, s.count, &out, 32)
            }
        }
        guard rc == 0 else { throw VaultError.keyFailed }
        return SymmetricKey(data: out)
    }

    private static func pbkdf2(_ password: String, salt: Data) throws -> SymmetricKey {
        var out = [UInt8](repeating: 0, count: 32)
        let rc = salt.withUnsafeBytes { s in
            CCKeyDerivationPBKDF(CCPBKDFAlgorithm(kCCPBKDF2), password, password.utf8.count,
                                 s.bindMemory(to: UInt8.self).baseAddress, s.count,
                                 CCPseudoRandomAlgorithm(kCCPRFHmacAlgSHA256), legacyIterations,
                                 &out, 32)
        }
        guard rc == kCCSuccess else { throw VaultError.keyFailed }
        return SymmetricKey(data: out)
    }
}

/// gzip, matching Python's `gzip.compress` / `gzip.decompress`.
enum Gzip {
    private static let chunk = 16 * 1024

    static func compress(_ data: Data) throws -> Data {
        var stream = z_stream()
        guard deflateInit2_(&stream, Z_DEFAULT_COMPRESSION, Z_DEFLATED, MAX_WBITS + 16, 8,
                            Z_DEFAULT_STRATEGY, ZLIB_VERSION, Int32(MemoryLayout<z_stream>.size)) == Z_OK
        else { throw VaultError.damaged }
        defer { deflateEnd(&stream) }
        return try run(&stream, data) { deflate(&$0, Z_FINISH) }
    }

    static func decompress(_ data: Data) throws -> Data {
        var stream = z_stream()
        // +32: accept a gzip or zlib header.
        guard inflateInit2_(&stream, MAX_WBITS + 32, ZLIB_VERSION, Int32(MemoryLayout<z_stream>.size)) == Z_OK
        else { throw VaultError.damaged }
        defer { inflateEnd(&stream) }
        return try run(&stream, data) { inflate(&$0, Z_NO_FLUSH) }
    }

    private static func run(_ stream: inout z_stream, _ input: Data,
                            _ step: (inout z_stream) -> Int32) throws -> Data {
        var bytes = [UInt8](input)
        if bytes.isEmpty { bytes = [0] }   // a valid pointer; avail_in stays 0 below
        var out = Data()
        var buffer = [UInt8](repeating: 0, count: chunk)
        try bytes.withUnsafeMutableBufferPointer { inBuf in
            stream.next_in = inBuf.baseAddress
            stream.avail_in = uInt(input.count)
            while true {
                let status: Int32 = buffer.withUnsafeMutableBufferPointer { outBuf in
                    stream.next_out = outBuf.baseAddress
                    stream.avail_out = uInt(outBuf.count)
                    let s = step(&stream)
                    out.append(outBuf.baseAddress!, count: outBuf.count - Int(stream.avail_out))
                    return s
                }
                if status == Z_STREAM_END { return }
                guard status == Z_OK else { throw VaultError.damaged }
                if stream.avail_in == 0 && stream.avail_out != 0 { throw VaultError.damaged }   // truncated
            }
        }
        return out
    }
}
