package app.securevault.android.data

import android.content.Context
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyPermanentlyInvalidatedException
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_STRONG
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import app.securevault.android.core.KdfParams
import app.securevault.android.core.VaultError
import app.securevault.android.core.VaultKey
import kotlinx.coroutines.suspendCancellableCoroutine
import java.security.GeneralSecurityException
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Fingerprint unlock: the derived vault key (never the master password) is
 * encrypted with an Android Keystore key that only a fingerprint check can
 * use. The Keystore key never leaves the secure hardware, is bound to this
 * device, and is invalidated as soon as a fingerprint is added or removed.
 * The encrypted blob is dropped whenever the vault or its master password
 * changes.
 */
class BiometricKey(context: Context) {
    private val prefs = context.getSharedPreferences("biometric", Context.MODE_PRIVATE)
    private val manager = BiometricManager.from(context)

    enum class Availability { READY, NOT_ENROLLED, UNAVAILABLE }

    val availability: Availability
        get() = when (manager.canAuthenticate(BIOMETRIC_STRONG)) {
            BiometricManager.BIOMETRIC_SUCCESS -> Availability.READY
            BiometricManager.BIOMETRIC_ERROR_NONE_ENROLLED -> Availability.NOT_ENROLLED
            else -> Availability.UNAVAILABLE
        }

    val isStored: Boolean get() = prefs.contains(BLOB)

    /** The salt of the stored key: a different one means the master password changed. */
    val storedSalt: ByteArray? get() = prefs.getString(SALT, null)?.let { decode(it) }

    /** A cipher for a brand-new Keystore key; the fingerprint prompt unlocks it for [save]. */
    fun encryptCipher(): Cipher {
        clear()
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE)
        val spec = KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .setUserAuthenticationRequired(true)
            .setInvalidatedByBiometricEnrollment(true)
            .apply {
                if (Build.VERSION.SDK_INT >= 30) {
                    setUserAuthenticationParameters(0, KeyProperties.AUTH_BIOMETRIC_STRONG)
                } else {
                    @Suppress("DEPRECATION")
                    setUserAuthenticationValidityDurationSeconds(-1)
                }
            }
            .build()
        generator.init(spec)
        val key = generator.generateKey()
        return Cipher.getInstance(TRANSFORMATION).apply { init(Cipher.ENCRYPT_MODE, key) }
    }

    /** Stores the vault key, encrypted with a cipher the fingerprint prompt unlocked. */
    fun save(cipher: Cipher, key: VaultKey) {
        val packed = key.salt + byteArrayOf(
            key.params.time.toByte(),
            (key.params.memoryKiB ushr 24).toByte(), (key.params.memoryKiB ushr 16).toByte(),
            (key.params.memoryKiB ushr 8).toByte(), key.params.memoryKiB.toByte(),
            key.params.parallelism.toByte(),
        ) + key.key
        val sealed = try {
            cipher.doFinal(packed)
        } catch (e: GeneralSecurityException) {
            throw VaultError.BiometricFailed("Couldn't store the key for fingerprint unlock.")
        } finally {
            packed.fill(0)
        }
        prefs.edit()
            .putString(BLOB, encode(sealed))
            .putString(IV, encode(cipher.iv))
            .putString(SALT, encode(key.salt))
            .apply()
    }

    /** A cipher the fingerprint prompt has to unlock before [load]; null when nothing is stored. */
    fun decryptCipher(): Cipher? {
        val iv = prefs.getString(IV, null) ?: return null
        val store = KeyStore.getInstance(KEYSTORE).apply { load(null) }
        val key = store.getKey(ALIAS, null) as? SecretKey ?: throw VaultError.FingerprintOutdated()
        return try {
            Cipher.getInstance(TRANSFORMATION).apply { init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, decode(iv))) }
        } catch (e: KeyPermanentlyInvalidatedException) {
            throw VaultError.FingerprintOutdated()
        }
    }

    fun load(cipher: Cipher): VaultKey {
        val sealed = prefs.getString(BLOB, null)?.let { decode(it) } ?: throw VaultError.FingerprintOutdated()
        val b = try {
            cipher.doFinal(sealed)
        } catch (e: GeneralSecurityException) {
            throw VaultError.FingerprintOutdated()
        }
        if (b.size != 16 + 6 + 32) throw VaultError.FingerprintOutdated()
        val memory = (b[17].toInt() and 0xFF shl 24) or (b[18].toInt() and 0xFF shl 16) or
            (b[19].toInt() and 0xFF shl 8) or (b[20].toInt() and 0xFF)
        val key = VaultKey(
            key = b.copyOfRange(22, 54),
            salt = b.copyOfRange(0, 16),
            params = KdfParams(b[16].toInt() and 0xFF, memory, b[21].toInt() and 0xFF),
        )
        b.fill(0)
        return key
    }

    fun clear() {
        prefs.edit().clear().apply()
        try {
            KeyStore.getInstance(KEYSTORE).apply { load(null) }.deleteEntry(ALIAS)
        } catch (e: Exception) {
            // Nothing stored.
        }
    }

    private fun encode(b: ByteArray) = Base64.encodeToString(b, Base64.NO_WRAP)
    private fun decode(s: String) = Base64.decode(s, Base64.NO_WRAP)

    private companion object {
        const val KEYSTORE = "AndroidKeyStore"
        const val ALIAS = "SecureVault.vaultKey"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val BLOB = "blob"
        const val IV = "iv"
        const val SALT = "salt"
    }
}

/**
 * Shows the system fingerprint prompt for `cipher`. Returns the unlocked
 * cipher, or null if the user cancelled or chose the master password.
 */
suspend fun FragmentActivity.authenticate(cipher: Cipher, title: String, subtitle: String?): Cipher? =
    suspendCancellableCoroutine { cont ->
        val prompt = BiometricPrompt(this, ContextCompat.getMainExecutor(this),
            object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                    if (cont.isActive) cont.resume(result.cryptoObject?.cipher)
                }

                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                    if (!cont.isActive) return
                    when (errorCode) {
                        BiometricPrompt.ERROR_USER_CANCELED, BiometricPrompt.ERROR_NEGATIVE_BUTTON,
                        BiometricPrompt.ERROR_CANCELED, BiometricPrompt.ERROR_TIMEOUT -> cont.resume(null)
                        else -> cont.resumeWithException(VaultError.BiometricFailed(errString.toString()))
                    }
                }
                // onAuthenticationFailed (a finger that didn't match): the prompt stays up.
            })
        val info = BiometricPrompt.PromptInfo.Builder()
            .setTitle(title)
            .apply { if (subtitle != null) setSubtitle(subtitle) }
            .setNegativeButtonText("Use master password")
            .setAllowedAuthenticators(BIOMETRIC_STRONG)
            .build()
        prompt.authenticate(info, BiometricPrompt.CryptoObject(cipher))
        cont.invokeOnCancellation { runOnUiThread { prompt.cancelAuthentication() } }
    }
