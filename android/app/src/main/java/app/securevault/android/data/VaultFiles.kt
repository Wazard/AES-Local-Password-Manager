package app.securevault.android.data

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import android.util.AtomicFile
import app.securevault.android.core.Backups
import app.securevault.android.core.VaultError
import app.securevault.android.core.VaultFormat
import java.io.File
import java.io.FileNotFoundException
import java.io.IOException

/**
 * Where the vault lives: a file in this app's private storage (`uri` null),
 * or one the user picked with the system file picker — the desktop's vault in
 * OneDrive, say — opened in place through a persisted permission, so the
 * phone and the PC edit the same file.
 */
data class VaultLocation(val uri: Uri?, val name: String) {
    val isExternal: Boolean get() = uri != null
}

class VaultFiles(private val context: Context) {
    private val prefs = context.getSharedPreferences("vault", Context.MODE_PRIVATE)
    private val resolver get() = context.contentResolver
    private val flags = Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION

    val localVault = File(context.filesDir, "vault.pwmanager")
    val backups = Backups(File(context.filesDir, "backups"))
    val localVaultExists: Boolean get() = localVault.exists()
    val local: VaultLocation get() = VaultLocation(null, localVault.name)

    /** The vault the app was last pointed at, if it can still be reached. */
    fun current(): VaultLocation? {
        prefs.getString(EXTERNAL, null)?.let { saved ->
            val uri = Uri.parse(saved)
            val granted = resolver.persistedUriPermissions.any {
                it.uri == uri && it.isReadPermission && it.isWritePermission
            }
            if (granted) return VaultLocation(uri, displayName(uri))
            forgetExternal()
        }
        return if (localVaultExists) local else null
    }

    /** Points the app at a file picked in the system file picker. */
    fun adopt(uri: Uri): VaultLocation {
        try {
            resolver.takePersistableUriPermission(uri, flags)
        } catch (e: SecurityException) {
            throw VaultError.Unreadable("Secure Vault can't keep access to that file. Pick it from a location that allows editing, such as the OneDrive app.")
        }
        val blob = try {
            readUri(uri)
        } catch (e: VaultError) {
            release(uri)
            throw e
        }
        if (!VaultFormat.looksLikeVault(blob)) {
            release(uri)
            throw VaultError.NotAVault()
        }
        prefs.getString(EXTERNAL, null)?.let { old -> if (old != uri.toString()) release(Uri.parse(old)) }
        prefs.edit().putString(EXTERNAL, uri.toString()).apply()
        return VaultLocation(uri, displayName(uri))
    }

    fun forgetExternal() {
        prefs.getString(EXTERNAL, null)?.let { release(Uri.parse(it)) }
        prefs.edit().remove(EXTERNAL).apply()
    }

    private fun release(uri: Uri) {
        try {
            resolver.releasePersistableUriPermission(uri, flags)
        } catch (e: SecurityException) {
            // Not held any more; nothing to release.
        }
    }

    // --- Reading and writing ------------------------------------------------

    fun read(location: VaultLocation): ByteArray {
        val uri = location.uri ?: return try {
            localVault.readBytes()
        } catch (e: IOException) {
            throw VaultError.Unreadable(e.message ?: "file error")
        }
        return readUri(uri)
    }

    private fun readUri(uri: Uri): ByteArray =
        try {
            resolver.openInputStream(uri)?.use { it.readBytes() } ?: throw VaultError.Unreadable("the file can't be opened")
        } catch (e: IOException) {
            throw VaultError.Unreadable(e.message ?: "file error")
        } catch (e: SecurityException) {
            throw VaultError.Unreadable("access to the file was withdrawn. Open it again.")
        }

    fun write(data: ByteArray, location: VaultLocation) {
        val uri = location.uri
        if (uri == null) {
            // Write-to-temp-then-rename, so a crash mid-save can't tear the file.
            val file = AtomicFile(localVault)
            val out = try {
                file.startWrite()
            } catch (e: IOException) {
                throw VaultError.Unreadable(e.message ?: "file error")
            }
            try {
                out.write(data)
                file.finishWrite(out)
            } catch (e: IOException) {
                file.failWrite(out)
                throw VaultError.Unreadable(e.message ?: "file error")
            }
            return
        }
        // A file in another app's storage (OneDrive, Drive) is written in place:
        // the picker grants access to that one file, not to its folder. Every
        // saved state is also kept as a backup, which covers a torn write.
        // "w" alone doesn't truncate on every provider, so only truncating modes.
        var lastError: Exception? = null
        for (mode in listOf("wt", "rwt")) {
            try {
                val out = resolver.openOutputStream(uri, mode) ?: continue
                out.use { it.write(data) }
                return
            } catch (e: FileNotFoundException) {
                lastError = e
            } catch (e: IllegalArgumentException) {
                lastError = e   // mode not supported by this provider
            } catch (e: IOException) {
                throw VaultError.Unreadable(e.message ?: "file error")
            } catch (e: SecurityException) {
                throw VaultError.Unreadable("access to the file was withdrawn. Open it again.")
            }
        }
        throw VaultError.Unreadable(lastError?.message ?: "the file can't be written")
    }

    private fun displayName(uri: Uri): String =
        try {
            resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
                if (c.moveToFirst()) c.getString(0) else null
            }
        } catch (e: Exception) {
            null
        } ?: "vault.pwmanager"

    private companion object {
        const val EXTERNAL = "externalVaultUri"
    }
}
