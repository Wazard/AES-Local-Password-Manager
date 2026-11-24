package app.securevault.android.core

import org.bouncycastle.crypto.digests.SHA256Digest
import org.bouncycastle.crypto.generators.Argon2BytesGenerator
import org.bouncycastle.crypto.generators.PKCS5S2ParametersGenerator
import org.bouncycastle.crypto.params.Argon2Parameters
import org.bouncycastle.crypto.params.KeyParameter
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.security.GeneralSecurityException
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.zip.GZIPInputStream
import java.util.zip.GZIPOutputStream
import javax.crypto.AEADBadTagException
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/*
 * The `.pwmanager` file format, byte for byte the same as the desktop app's
 * core/encryption.py (and the iOS app's VaultFormat.swift), so one vault file
 * works everywhere.
 *
 *     v2: "PWV2" | time(1) | memory KiB(4, big-endian) | lanes(1) | salt(16)
 *              | nonce(12) | AES-256-GCM ciphertext + tag
 *     v1 (legacy): salt(16) | nonce(12) | ciphertext + tag, PBKDF2-SHA256
 *
 * The plaintext is gzip-compressed JSON: { service: {user, pass, url, ...} }.
 */

data class KdfParams(val time: Int, val memoryKiB: Int, val parallelism: Int) {
    companion object {
        /** Argon2id defaults, same as the desktop: 64 MiB, 3 passes, 4 lanes. */
        val STANDARD = KdfParams(time = 3, memoryKiB = 64 * 1024, parallelism = 4)
    }
}

/**
 * What a save needs: the key derived at unlock, plus the salt and parameters
 * it came from (they go into every file header). The master password itself
 * is discarded once this exists.
 */
class VaultKey(val key: ByteArray, val salt: ByteArray, val params: KdfParams)

open class VaultError(message: String) : Exception(message) {
    class WrongPassword : VaultError("Wrong master password.")
    class NotAVault : VaultError("That file doesn't look like a Secure Vault file.")
    class Damaged : VaultError("The vault file is damaged and can't be read.")
    class KeyFailed : VaultError("Couldn't derive the vault key.")
    class ChangedElsewhere : VaultError(
        "The vault was changed on another device with a different master password. " +
            "Lock the app and unlock it with the new password. Your last change was not saved."
    )
    class FingerprintOutdated : VaultError(
        "Fingerprint unlock needs setting up again — the master password or the enrolled " +
            "fingerprints changed. Unlock with your password, then turn it back on in Settings."
    )
    class BiometricFailed(why: String) : VaultError(why)
    class Locked : VaultError("The vault is locked.")
    class Duplicate(name: String) : VaultError("An account named “$name” already exists.")
    class EntryGone : VaultError(
        "That account no longer exists — it may have been deleted on another device."
    )
    class AlreadyExists : VaultError("A vault already exists in this app. Open it instead.")
    class Unreadable(why: String) : VaultError("Couldn't read the vault: $why")
}

object VaultFormat {
    private val MAGIC = "PWV2".toByteArray(Charsets.US_ASCII)
    const val HEADER_LENGTH = 4 + 1 + 4 + 1 + 16
    private const val LEGACY_ITERATIONS = 100_000
    private val random = SecureRandom()

    class Opened(
        val payload: ByteArray,
        /** The key future saves use. For a legacy file it is fresh Argon2id
         *  material, so the next save migrates the file, like the desktop does. */
        val key: VaultKey,
        val migrated: Boolean,
    )

    private fun hasMagic(blob: ByteArray) =
        blob.size >= 4 && (0 until 4).all { blob[it] == MAGIC[it] }

    /** The same cheap check the desktop does before adopting a picked file. */
    fun looksLikeVault(blob: ByteArray) = hasMagic(blob) || blob.size > 28

    fun open(blob: ByteArray, password: String): Opened {
        val header = parseHeader(blob)
        if (header != null) {
            val key = argon2id(password, header.first, header.second)
            val payload = decrypt(blob.copyOfRange(HEADER_LENGTH, blob.size), key)
            return Opened(payload, VaultKey(key, header.first, header.second), migrated = false)
        }
        if (blob.size <= 28 + 16) throw VaultError.NotAVault()
        val legacyKey = pbkdf2(password, blob.copyOfRange(0, 16))
        val payload = decrypt(blob.copyOfRange(16, blob.size), legacyKey)
        return Opened(payload, newKey(password), migrated = true)
    }

    /** Opens a v2 file with a key already in hand (fingerprint unlock, or picking
     *  up a save made on another device). Fails if the file was re-keyed. */
    fun open(blob: ByteArray, key: VaultKey): ByteArray {
        val header = parseHeader(blob)
        if (header == null || !header.first.contentEquals(key.salt) || header.second != key.params) {
            throw VaultError.ChangedElsewhere()
        }
        return decrypt(blob.copyOfRange(HEADER_LENGTH, blob.size), key.key)
    }

    fun seal(payload: ByteArray, key: VaultKey): ByteArray {
        val out = ByteArrayOutputStream()
        out.write(MAGIC)
        out.write(key.params.time)
        out.write(byteArrayOf(
            (key.params.memoryKiB ushr 24).toByte(), (key.params.memoryKiB ushr 16).toByte(),
            (key.params.memoryKiB ushr 8).toByte(), key.params.memoryKiB.toByte(),
        ))
        out.write(key.params.parallelism)
        out.write(key.salt)
        out.write(Aead.seal(key.key, payload))   // nonce | ciphertext | tag, as Python's AESGCM
        return out.toByteArray()
    }

    /** A fresh salt and the standard parameters (new vault, or a new master password). */
    fun newKey(password: String): VaultKey {
        val salt = ByteArray(16).also(random::nextBytes)
        val params = KdfParams.STANDARD
        return VaultKey(argon2id(password, salt, params), salt, params)
    }

    /** Re-derives a key to check a password against the vault's own salt. */
    fun matches(password: String, key: VaultKey): Boolean =
        try {
            MessageDigest.isEqual(argon2id(password, key.salt, key.params), key.key)
        } catch (e: VaultError) {
            false
        }

    private fun parseHeader(b: ByteArray): Pair<ByteArray, KdfParams>? {
        if (b.size < HEADER_LENGTH + 12 + 16 || !hasMagic(b)) return null
        val memory = (b[5].toInt() and 0xFF shl 24) or (b[6].toInt() and 0xFF shl 16) or
            (b[7].toInt() and 0xFF shl 8) or (b[8].toInt() and 0xFF)
        val params = KdfParams(b[4].toInt() and 0xFF, memory, b[9].toInt() and 0xFF)
        return b.copyOfRange(10, 26) to params
    }

    private fun decrypt(combined: ByteArray, key: ByteArray): ByteArray =
        try {
            Aead.open(key, combined)
        } catch (e: GeneralSecurityException) {
            throw VaultError.WrongPassword()
        }

    fun argon2id(password: String, salt: ByteArray, params: KdfParams): ByteArray {
        try {
            val generator = Argon2BytesGenerator()
            generator.init(
                Argon2Parameters.Builder(Argon2Parameters.ARGON2_id)
                    .withVersion(Argon2Parameters.ARGON2_VERSION_13)
                    .withIterations(params.time)
                    .withMemoryAsKB(params.memoryKiB)
                    .withParallelism(params.parallelism)
                    .withSalt(salt)
                    .build()
            )
            val out = ByteArray(32)
            generator.generateBytes(password.toByteArray(Charsets.UTF_8), out)
            return out
        } catch (e: RuntimeException) {
            throw VaultError.KeyFailed()
        }
    }

    private fun pbkdf2(password: String, salt: ByteArray): ByteArray {
        val generator = PKCS5S2ParametersGenerator(SHA256Digest())
        generator.init(password.toByteArray(Charsets.UTF_8), salt, LEGACY_ITERATIONS)
        return (generator.generateDerivedMacParameters(256) as KeyParameter).key
    }
}

/** AES-256-GCM with a random 12-byte nonce in front: nonce | ciphertext | tag. */
object Aead {
    private val random = SecureRandom()
    private const val TRANSFORMATION = "AES/GCM/NoPadding"

    fun seal(key: ByteArray, plaintext: ByteArray): ByteArray {
        val nonce = ByteArray(12).also(random::nextBytes)
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, nonce))
        return nonce + cipher.doFinal(plaintext)
    }

    fun open(key: ByteArray, combined: ByteArray): ByteArray {
        if (combined.size < 12 + 16) throw AEADBadTagException("too short")
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, combined, 0, 12))
        return cipher.doFinal(combined, 12, combined.size - 12)
    }
}

/** gzip, matching Python's `gzip.compress` / `gzip.decompress`. */
object Gzip {
    fun compress(data: ByteArray): ByteArray {
        val out = ByteArrayOutputStream()
        GZIPOutputStream(out).use { it.write(data) }
        return out.toByteArray()
    }

    fun decompress(data: ByteArray): ByteArray =
        try {
            GZIPInputStream(ByteArrayInputStream(data)).use { it.readBytes() }
        } catch (e: IOException) {
            throw VaultError.Damaged()
        }
}

fun sha256(data: ByteArray): ByteArray = MessageDigest.getInstance("SHA-256").digest(data)
