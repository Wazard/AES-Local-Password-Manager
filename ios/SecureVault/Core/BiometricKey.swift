import Foundation
import CryptoKit
import LocalAuthentication
import Security

/// Face ID / Touch ID unlock: the derived vault key (never the master
/// password) sits in the Keychain behind a biometric check. It is bound to the
/// current set of enrolled faces/fingers and to this device, and is dropped
/// whenever the vault or its master password changes.
enum BiometricKey {
    private static let service = "SecureVault.vaultKey"
    private static let account = "vault"

    static var biometryName: String {
        let context = LAContext()
        _ = context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: nil)
        return context.biometryType == .touchID ? "Touch ID" : "Face ID"
    }

    static var isAvailable: Bool {
        LAContext().canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: nil)
    }

    static func save(_ key: VaultKey) throws {
        clear()
        guard let access = SecAccessControlCreateWithFlags(
            nil, kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly, .biometryCurrentSet, nil)
        else { throw VaultError.keyFailed }
        var blob = key.salt
        blob.append(key.params.time)
        withUnsafeBytes(of: key.params.memoryKiB.bigEndian) { blob.append(contentsOf: $0) }
        blob.append(key.params.parallelism)
        key.key.withUnsafeBytes { blob.append(contentsOf: $0) }
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecAttrAccessControl as String: access,
            kSecValueData as String: blob,
        ]
        guard SecItemAdd(query as CFDictionary, nil) == errSecSuccess else { throw VaultError.keyFailed }
    }

    /// Shows the Face ID prompt. Blocks, so call it off the main thread.
    /// Returns nil if the user cancelled.
    static func load() throws -> VaultKey? {
        let context = LAContext()
        context.localizedReason = "Unlock your vault"
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecUseAuthenticationContext as String: context,
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        // Cancelled, failed, or asked while the app wasn't in front: just stay locked.
        if [errSecUserCanceled, errSecAuthFailed, errSecInteractionNotAllowed].contains(status) { return nil }
        guard status == errSecSuccess, let data = item as? Data, data.count == 16 + 6 + 32 else {
            throw VaultError.faceIDOutdated
        }
        let b = [UInt8](data)
        let memory = UInt32(b[17]) << 24 | UInt32(b[18]) << 16 | UInt32(b[19]) << 8 | UInt32(b[20])
        return VaultKey(key: SymmetricKey(data: b[22..<54]),
                        salt: Data(b[0..<16]),
                        params: KDFParams(time: b[16], memoryKiB: memory, parallelism: b[21]))
    }

    static func clear() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
    }
}
