package app.securevault.android

import android.app.Application
import android.content.ClipData
import android.content.ClipDescription
import android.content.ClipboardManager
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.PersistableBundle
import android.os.SystemClock
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.ProcessLifecycleOwner
import androidx.lifecycle.viewModelScope
import app.securevault.android.core.BackupFile
import app.securevault.android.core.Entry
import app.securevault.android.core.SessionCrypto
import app.securevault.android.core.SortMode
import app.securevault.android.core.Search
import app.securevault.android.core.VaultCodec
import app.securevault.android.core.VaultError
import app.securevault.android.core.VaultFormat
import app.securevault.android.core.VaultKey
import app.securevault.android.core.sha256
import app.securevault.android.data.BiometricKey
import app.securevault.android.data.ReceivedVault
import app.securevault.android.data.VaultFiles
import app.securevault.android.data.VaultLocation
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import javax.crypto.Cipher

enum class Phase { SETUP, LOCKED, UNLOCKED }

/** Shows the fingerprint prompt for a cipher; null if the user cancelled. */
typealias Authenticate = suspend (Cipher) -> Cipher?

/**
 * The app's state and every vault operation — the Android counterpart of the
 * iOS app's VaultStore.swift, with the same rules.
 */
class VaultStore(app: Application) : AndroidViewModel(app) {
    val files = VaultFiles(app)
    val biometric = BiometricKey(app)
    private val prefs = app.getSharedPreferences("settings", Context.MODE_PRIVATE)

    var phase by mutableStateOf(Phase.SETUP)
        private set
    var location by mutableStateOf<VaultLocation?>(null)
        private set
    var entries by mutableStateOf<List<Entry>>(emptyList())
        private set
    var busy by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
    var toast by mutableStateOf<String?>(null)
        private set
    var fingerprintEnabled by mutableStateOf(false)
        private set

    // Settings, same defaults as on iOS.
    var lockGraceSeconds by mutableIntStateOf(prefs.getInt(LOCK_GRACE, 30))
        private set
    var clipboardSeconds by mutableIntStateOf(prefs.getInt(CLIPBOARD, 60))
        private set
    var sort by mutableStateOf(SortMode.fromRaw(prefs.getString(SORT, null)))
        private set

    private var key: VaultKey? = null
    private var session = SessionCrypto()
    /** Hash of the file as we last read or wrote it — how a save notices that
     *  another device (the PC, through OneDrive) saved in the meantime. */
    private var lastHash: ByteArray? = null
    private var backgroundedAt: Long? = null
    private val saving = Mutex()
    private val main = Handler(Looper.getMainLooper())

    private val lifecycleObserver = LifecycleEventObserver { _, event ->
        when (event) {
            Lifecycle.Event.ON_STOP -> wentToBackground()
            Lifecycle.Event.ON_START -> cameToForeground()
            else -> {}
        }
    }

    init {
        val found = files.current()
        location = found
        phase = if (found == null) Phase.SETUP else Phase.LOCKED
        fingerprintEnabled = prefs.getBoolean(FINGERPRINT, false) && biometric.isStored
        // The whole app leaving the screen, not one activity (a rotation doesn't count).
        ProcessLifecycleOwner.get().lifecycle.addObserver(lifecycleObserver)
    }

    override fun onCleared() {
        ProcessLifecycleOwner.get().lifecycle.removeObserver(lifecycleObserver)
    }

    // --- Choosing a vault ---------------------------------------------------

    fun adopt(uri: Uri) = launchWorking {
        val found = withContext(Dispatchers.IO) { files.adopt(uri) }
        switchTo(found)
    }

    fun useLocalVault() {
        files.forgetExternal()
        switchTo(if (files.localVaultExists) files.local else null)
    }

    fun chooseAnotherVault() {
        lock()
        phase = Phase.SETUP
    }

    private fun switchTo(newLocation: VaultLocation?) {
        lock()
        if (newLocation != location) disableFingerprint()
        location = newLocation
        phase = if (newLocation == null) Phase.SETUP else Phase.LOCKED
    }

    // --- Unlocking ----------------------------------------------------------

    fun create(password: String) = launchWorking {
        if (files.localVaultExists) throw VaultError.AlreadyExists()
        val newKey = withContext(Dispatchers.Default) { VaultFormat.newKey(password) }
        val target = files.local
        val s = SessionCrypto()
        val blob = VaultCodec.seal(emptyList(), s, newKey)
        withContext(Dispatchers.IO) {
            files.write(blob, target)
            files.backups.make(blob)
        }
        files.forgetExternal()
        disableFingerprint()
        location = target
        session = s
        entries = emptyList()
        key = newKey
        lastHash = sha256(blob)
        phase = Phase.UNLOCKED
    }

    fun unlock(password: String) = launchWorking {
        val target = location ?: return@launchWorking
        val (blob, opened) = withContext(Dispatchers.Default) {
            val blob = files.read(target)
            blob to VaultFormat.open(blob, password)
        }
        load(opened.payload, blob, opened.key)
        // The stored fingerprint key can only be replaced with a fingerprint,
        // so if the master password changed it is dropped instead.
        if (fingerprintEnabled && biometric.storedSalt?.contentEquals(opened.key.salt) != true) {
            disableFingerprint()
            showToast("Fingerprint unlock is off: the master password changed")
        }
        phase = Phase.UNLOCKED
    }

    fun unlockWithFingerprint(authenticate: Authenticate) = launchWorking {
        val target = location ?: return@launchWorking
        if (!fingerprintEnabled) return@launchWorking
        val stored: VaultKey
        try {
            val cipher = biometric.decryptCipher() ?: throw VaultError.FingerprintOutdated()
            val unlocked = authenticate(cipher) ?: return@launchWorking
            stored = biometric.load(unlocked)
        } catch (e: VaultError.FingerprintOutdated) {
            disableFingerprint()
            throw e
        }
        val blob = withContext(Dispatchers.IO) { files.read(target) }
        val payload = try {
            withContext(Dispatchers.Default) { VaultFormat.open(blob, stored) }
        } catch (e: VaultError.ChangedElsewhere) {
            disableFingerprint()
            throw VaultError.FingerprintOutdated()
        }
        load(payload, blob, stored)
        phase = Phase.UNLOCKED
    }

    private suspend fun load(payload: ByteArray, blob: ByteArray, vaultKey: VaultKey) {
        val s = SessionCrypto()
        val loaded = withContext(Dispatchers.Default) { VaultCodec.open(payload, s) }
        session = s
        entries = loaded
        key = vaultKey
        lastHash = sha256(blob)
    }

    fun lock() {
        entries = emptyList()
        key = null
        session = SessionCrypto()
        lastHash = null
        if (phase == Phase.UNLOCKED) phase = Phase.LOCKED
    }

    private fun wentToBackground() {
        if (lockGraceSeconds == 0) lock() else if (backgroundedAt == null) backgroundedAt = SystemClock.elapsedRealtime()
    }

    private fun cameToForeground() {
        val since = backgroundedAt
        if (since != null && SystemClock.elapsedRealtime() - since >= lockGraceSeconds * 1000L) lock()
        backgroundedAt = null
    }

    // --- Passwords ----------------------------------------------------------

    fun password(entry: Entry): String = session.open(entry.sealedPassword)

    /** Copies to the clipboard, marked sensitive (Android 13+ hides the preview),
     *  and clears it after the chosen delay unless something else was copied since. */
    fun copy(text: String, label: String) {
        val clipboard = getApplication<Application>().getSystemService(ClipboardManager::class.java) ?: return
        val clip = ClipData.newPlainText(CLIP_LABEL, text)
        clip.description.extras = PersistableBundle().apply {
            putBoolean(ClipDescription.EXTRA_IS_SENSITIVE, true)
        }
        clipboard.setPrimaryClip(clip)
        main.removeCallbacksAndMessages(CLIP_TOKEN)
        if (clipboardSeconds > 0) {
            main.postAtTime({
                val current = try {
                    clipboard.primaryClipDescription
                } catch (e: SecurityException) {
                    null
                }
                // Unreadable in the background: clear it anyway, it's ours or stale.
                if (current == null || current.label == CLIP_LABEL) {
                    if (Build.VERSION.SDK_INT >= 28) clipboard.clearPrimaryClip()
                    else clipboard.setPrimaryClip(ClipData.newPlainText("", ""))
                }
            }, CLIP_TOKEN, SystemClock.uptimeMillis() + clipboardSeconds * 1000L)
        }
        // Android 13 and later confirm a copy themselves.
        if (Build.VERSION.SDK_INT < 33) showToast("$label copied")
    }

    fun showToast(message: String) {
        toast = message
        viewModelScope.launch {
            delay(1600)
            if (toast == message) toast = null
        }
    }

    // --- Editing ------------------------------------------------------------

    /**
     * Every edit goes through here. The change is applied to the vault as it
     * is on disk *now*: if another device saved since we loaded, its version
     * is picked up first, so its edits are kept instead of overwritten.
     * Changes must therefore find entries by name, not by id.
     */
    fun perform(change: (MutableList<Entry>) -> Unit, onDone: (Boolean) -> Unit = {}) {
        viewModelScope.launch {
            val ok = try {
                commit(null, change)
                true
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                report(e)
                false
            }
            onDone(ok)
        }
    }

    private suspend fun commit(rekey: VaultKey?, change: (MutableList<Entry>) -> Unit) = saving.withLock {
        val current = key ?: throw VaultError.Locked()
        val target = location ?: throw VaultError.Locked()
        val onDisk = withContext(Dispatchers.IO) { files.read(target) }
        var working = entries.toMutableList()
        if (!sha256(onDisk).contentEquals(lastHash)) {
            val fresh = withContext(Dispatchers.Default) {
                VaultCodec.open(VaultFormat.open(onDisk, current), session)
            }
            // Keep ids stable for entries that are still there, so open screens stay put.
            val ids = entries.associate { it.name to it.id }
            working = fresh.map { e -> ids[e.name]?.let { e.copy(id = it) } ?: e }.toMutableList()
        }
        change(working)
        val saveKey = rekey ?: current
        val blob = withContext(Dispatchers.Default) { VaultCodec.seal(working, session, saveKey) }
        withContext(Dispatchers.IO) { files.write(blob, target) }
        entries = working.toList()
        key = saveKey
        lastHash = sha256(blob)
        withContext(Dispatchers.IO) { files.backups.make(blob) }
    }

    fun toggleFavourite(name: String) = perform({ list ->
        val i = list.indexOfFirst { it.name == name }
        if (i < 0) throw VaultError.EntryGone()
        list[i] = list[i].copy(favourite = !list[i].favourite).markedChanged()
    })

    /**
     * In a vault kept in this app, an account the PC may have is only marked
     * deleted, so the next sync deletes it there too; it disappears for good
     * when the PC sends the merged vault back. One created here and never
     * synced, or one in a vault opened from a picked file (the PC's own file),
     * is simply removed.
     */
    fun delete(name: String, onDone: (Boolean) -> Unit = {}) {
        val keepTombstone = location?.isExternal == false
        perform({ list ->
            val i = list.indexOfFirst { it.name == name }
            if (i < 0) return@perform
            if (keepTombstone && list[i].syncState != "new") {
                list[i] = list[i].copy(syncState = "deleted")
            } else {
                list.removeAt(i)
            }
        }, onDone)
    }

    /**
     * Add (`original` null) or edit. `newPassword` null keeps the stored
     * password, which then isn't even decrypted. `onDone` gets null on
     * success, or what to tell the user.
     */
    fun saveEntry(
        original: String?,
        name: String,
        user: String,
        url: String,
        newPassword: String?,
        onDone: (String?) -> Unit,
    ) {
        val newName = name.trim()
        if (newName.isEmpty()) return onDone("Give the account a name.")
        if (newName != original && entries.any { it.name == newName && !it.isDeleted }) {
            return onDone(VaultError.Duplicate(newName).message)
        }
        val sealed = newPassword?.let { session.seal(it) }
        val site = url.trim()
        viewModelScope.launch {
            val problem = try {
                commit(null) { list ->
                    if (newName != original && list.any { it.name == newName && !it.isDeleted }) {
                        throw VaultError.Duplicate(newName)
                    }
                    // Reusing the name of an account deleted here: the PC still has
                    // that name, so this becomes an edit of it rather than a new one.
                    var reusesDeleted = false
                    if (newName != original) {
                        val t = list.indexOfFirst { it.name == newName && it.isDeleted }
                        if (t >= 0) {
                            list.removeAt(t)
                            reusesDeleted = true
                        }
                    }
                    if (original != null) {
                        // Edited in place, so a rename keeps the entry's spot in the vault.
                        val i = list.indexOfFirst { it.name == original && !it.isDeleted }
                        if (i < 0) throw VaultError.EntryGone()
                        var e = list[i]
                        if (newName != original && e.renamedFrom == null && e.syncState != "new") {
                            e = e.copy(renamedFrom = original)   // the name the PC knows it by
                        }
                        e = e.copy(name = newName, user = user, url = site,
                            sealedPassword = sealed ?: e.sealedPassword).markedChanged()
                        if (reusesDeleted) e = e.copy(syncState = "changed")
                        list[i] = e
                    } else {
                        list.add(Entry(
                            name = newName, user = user, url = site, favourite = false,
                            created = Entry.nowStamp(), sealedPassword = sealed ?: ByteArray(0),
                            syncState = if (reusesDeleted) "changed" else "new",
                        ))
                    }
                }
                null
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                e.message ?: e.toString()
            }
            onDone(problem)
        }
    }

    /** Accounts changed here since the last sync with the PC. */
    val unsyncedCount: Int get() = entries.count { it.syncState != null }

    /** After a sync the file holds the merged vault: show it (same key, as the
     *  PC opened the phone's copy with its own). Locks if that fails. */
    fun reloadAfterSync() {
        if (phase != Phase.UNLOCKED) return
        val current = key ?: return
        val target = location ?: return
        viewModelScope.launch {
            try {
                val blob = withContext(Dispatchers.IO) { files.read(target) }
                val payload = withContext(Dispatchers.Default) { VaultFormat.open(blob, current) }
                load(payload, blob, current)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                lock()
            }
        }
    }

    fun changeMasterPassword(current: String, new: String, onDone: (Boolean) -> Unit) {
        val vaultKey = key ?: return onDone(false)
        launchWorking {
            val matches = withContext(Dispatchers.Default) { VaultFormat.matches(current, vaultKey) }
            if (!matches) throw VaultError.WrongPassword()
            val newKey = withContext(Dispatchers.Default) { VaultFormat.newKey(new) }
            commit(newKey) { }
            if (fingerprintEnabled) {
                disableFingerprint()
                showToast("Master password changed. Turn fingerprint unlock on again in Settings.")
            } else {
                showToast("Master password changed")
            }
            onDone(true)
        }
    }

    // --- Settings -----------------------------------------------------------

    fun setFingerprint(on: Boolean, authenticate: Authenticate) {
        if (!on) return disableFingerprint()
        val vaultKey = key ?: return
        launchWorking {
            val cipher = biometric.encryptCipher()
            val unlocked = authenticate(cipher)
            if (unlocked == null) {
                biometric.clear()
                return@launchWorking
            }
            biometric.save(unlocked, vaultKey)
            prefs.edit().putBoolean(FINGERPRINT, true).apply()
            fingerprintEnabled = true
        }
    }

    private fun disableFingerprint() {
        biometric.clear()
        prefs.edit().putBoolean(FINGERPRINT, false).apply()
        fingerprintEnabled = false
    }

    fun updateLockGrace(seconds: Int) {
        lockGraceSeconds = seconds
        prefs.edit().putInt(LOCK_GRACE, seconds).apply()
    }

    fun updateClipboardSeconds(seconds: Int) {
        clipboardSeconds = seconds
        prefs.edit().putInt(CLIPBOARD, seconds).apply()
    }

    fun updateSort(mode: SortMode) {
        sort = mode
        prefs.edit().putString(SORT, mode.raw).apply()
    }

    fun generatorOption(name: String, default: Boolean) = prefs.getBoolean("gen.$name", default)
    fun setGeneratorOption(name: String, value: Boolean) = prefs.edit().putBoolean("gen.$name", value).apply()
    var generatorLength: Int
        get() = prefs.getInt("gen.length", 18)
        set(value) = prefs.edit().putInt("gen.length", value).apply()

    /**
     * Puts a backup back as the live vault, then locks: the restored copy may
     * have a different master password. The current state is backed up first,
     * so restoring the wrong one can be undone.
     */
    fun restore(backup: BackupFile) {
        val target = location ?: return
        launchWorking {
            withContext(Dispatchers.IO) {
                val blob = files.backups.read(backup)
                try {
                    files.backups.make(files.read(target))
                } catch (e: VaultError) {
                    // Nothing readable to keep.
                }
                files.write(blob, target)
            }
            lock()
            showToast("Backup restored")
        }
    }

    /**
     * Makes a vault sent from the PC the one this app uses: it is written to
     * the app's own storage (the vault already there is backed up first) and
     * the app switches to it, locked, ready for that vault's master password.
     */
    fun installReceived(received: ReceivedVault, onDone: () -> Unit) {
        launchWorking {
            val target = files.local
            withContext(Dispatchers.IO) {
                if (files.localVaultExists) {
                    try {
                        files.backups.make(files.read(target))
                    } catch (e: VaultError) {
                        // Unreadable: nothing to keep.
                    }
                }
                files.write(received.data, target)
            }
            files.forgetExternal()
            lock()
            disableFingerprint()
            location = target
            phase = Phase.LOCKED
            showToast("Vault received from ${received.sender}")
            onDone()
        }
    }

    // --- Helpers ------------------------------------------------------------

    private fun launchWorking(body: suspend () -> Unit) {
        viewModelScope.launch {
            busy = true
            try {
                body()
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                report(e)
            } finally {
                busy = false
            }
        }
    }

    private fun report(e: Exception) {
        error = e.message ?: e.toString()
    }

    fun visible(query: String): List<Entry> = Search.visible(entries, query, sort)

    fun entry(id: String): Entry? = entries.firstOrNull { it.id == id && !it.isDeleted }

    private companion object {
        const val LOCK_GRACE = "lockGraceSeconds"
        const val CLIPBOARD = "clipboardSeconds"
        const val FINGERPRINT = "fingerprintEnabled"
        const val SORT = "sortMode"
        const val CLIP_LABEL = "Secure Vault"
        val CLIP_TOKEN = Any()
    }
}
