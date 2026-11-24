package app.securevault.android.ui

import android.text.format.Formatter
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.securevault.android.Authenticate
import app.securevault.android.BuildConfig
import app.securevault.android.VaultStore
import app.securevault.android.core.BackupFile
import app.securevault.android.core.PasswordStrength
import app.securevault.android.data.BiometricKey
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle

@Composable
fun SettingsScreen(
    store: VaultStore,
    authenticate: Authenticate,
    pickVault: () -> Unit,
    onBack: () -> Unit,
    onReceive: () -> Unit,
    changeMaster: () -> Unit,
    backups: () -> Unit,
) {
    val location = store.location

    Scaffold(containerColor = Palette.background, topBar = { Bar("Settings", onBack) }) { padding ->
        Column(Modifier.padding(padding).verticalScroll(rememberScrollState()).padding(16.dp)) {
            Section(
                "Vault",
                footer = "A vault opened from a file (for example from OneDrive) is edited in place, so the PC sees the same accounts. Switching vaults locks the app.",
            ) {
                SectionRow("File", location?.name ?: "—")
                HorizontalDivider()
                SectionRow("Stored", if (location?.isExternal == true) "Opened from a file" else "On this device")
                HorizontalDivider()
                SectionRow("Open a different vault…", color = Palette.primary, onClick = pickVault)
                if (location?.isExternal == true && store.files.localVaultExists) {
                    HorizontalDivider()
                    SectionRow("Switch to the vault on this device", color = Palette.primary, onClick = { store.useLocalVault() })
                }
            }

            val unsynced = store.unsyncedCount
            Section(
                "Sync",
                footer = if (unsynced == 0) "Everything here is already on the PC."
                else "$unsynced account(s) added, changed or deleted here since the last sync. Syncing sends them to the PC's vault and brings back what's new there.",
            ) {
                Box(Modifier.padding(12.dp)) {
                    SecondaryButton("Sync with PC over Wi-Fi", onClick = onReceive, icon = Icons.Filled.Sync)
                }
            }

            Section("Security") {
                when (store.biometric.availability) {
                    BiometricKey.Availability.READY -> {
                        ToggleRow("Unlock with fingerprint", store.fingerprintEnabled, enabled = !store.busy) {
                            store.setFingerprint(it, authenticate)
                        }
                        HorizontalDivider()
                    }
                    BiometricKey.Availability.NOT_ENROLLED -> {
                        ToggleRow("Unlock with fingerprint", false, enabled = false) {}
                        Text("Add a fingerprint in Android's settings to use it here.", fontSize = 13.sp,
                            color = Palette.secondaryText, modifier = Modifier.padding(start = 16.dp, end = 16.dp, bottom = 8.dp))
                        HorizontalDivider()
                    }
                    BiometricKey.Availability.UNAVAILABLE -> {}
                }
                Choice(
                    "Lock after leaving the app", store.lockGraceSeconds,
                    listOf(0 to "Immediately", 30 to "30 seconds", 60 to "1 minute", 300 to "5 minutes"),
                    store::updateLockGrace,
                )
                HorizontalDivider()
                Choice(
                    "Clear copied passwords", store.clipboardSeconds,
                    listOf(30 to "After 30 seconds", 60 to "After 1 minute", 120 to "After 2 minutes", 0 to "Never"),
                    store::updateClipboardSeconds,
                )
                HorizontalDivider()
                SectionRow("Change master password", color = Palette.primary, onClick = changeMaster)
            }

            Section(null, footer = "Every save keeps a dated copy inside the app, using the same names and retention rules as the desktop.") {
                SectionRow("Backups", color = Palette.primary, onClick = backups)
            }

            Section(null) {
                SectionRow("Version", BuildConfig.VERSION_NAME)
            }
        }
    }
}

/** A row showing the current choice; tapping it lists the others. */
@Composable
private fun Choice(title: String, value: Int, options: List<Pair<Int, String>>, onChange: (Int) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Box {
        SectionRow(title, options.firstOrNull { it.first == value }?.second ?: "$value s", onClick = { open = true })
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            for ((seconds, label) in options) {
                DropdownMenuItem(text = { Text(label) }, onClick = {
                    open = false
                    onChange(seconds)
                })
            }
        }
    }
}

@Composable
fun ChangeMasterScreen(store: VaultStore, onBack: () -> Unit) {
    var current by remember { mutableStateOf("") }
    var new by remember { mutableStateOf("") }
    var confirm by remember { mutableStateOf("") }
    val ok = current.isNotEmpty() && PasswordStrength.evaluate(new).ok && new == confirm

    Scaffold(containerColor = Palette.background, topBar = { Bar("Master password", onBack) }) { padding ->
        Column(
            verticalArrangement = Arrangement.spacedBy(12.dp),
            modifier = Modifier.padding(padding).imePadding().verticalScroll(rememberScrollState()).padding(16.dp),
        ) {
            PasswordField(current, { current = it }, "Current master password")
            PasswordField(new, { new = it }, "New master password")
            StrengthMeter(new)
            PasswordField(confirm, { confirm = it }, "Confirm new password", imeAction = ImeAction.Done)
            if (confirm.isNotEmpty() && confirm != new) {
                Text("The passwords don't match.", fontSize = 12.sp, color = Palette.negative)
            }
            Text("The PC app keeps the old password until you lock and unlock it there.",
                fontSize = 13.sp, color = Palette.secondaryText)
            PrimaryButton("Change master password", busy = store.busy, enabled = ok, onClick = {
                store.changeMasterPassword(current, new) { done -> if (done) onBack() }
            })
        }
    }
}

@Composable
fun BackupsScreen(store: VaultStore, onBack: () -> Unit) {
    val backups = remember { store.files.backups.list() }
    var pending by remember { mutableStateOf<BackupFile?>(null) }
    val context = LocalContext.current
    val format = remember { DateTimeFormatter.ofLocalizedDateTime(FormatStyle.MEDIUM, FormatStyle.SHORT) }

    Scaffold(containerColor = Palette.background, topBar = { Bar("Backups", onBack) }) { padding ->
        Column(Modifier.padding(padding).verticalScroll(rememberScrollState()).padding(16.dp)) {
            if (backups.isEmpty()) {
                Text("No backups yet. One is made every time the vault is saved from this device.",
                    color = Palette.secondaryText)
            } else {
                Section(null) {
                    backups.forEachIndexed { i, b ->
                        if (i > 0) HorizontalDivider()
                        SectionRow(b.date.format(format), Formatter.formatShortFileSize(context, b.size),
                            onClick = { pending = b })
                    }
                }
            }
        }
    }

    pending?.let { b ->
        AlertDialog(
            onDismissRequest = { pending = null },
            title = { Text("Restore this backup?") },
            text = { Text("The vault as it is now is backed up first. The app then locks — unlock with the master password the backup was saved with.") },
            confirmButton = {
                TextButton(onClick = {
                    pending = null
                    store.restore(b)
                }) { Text("Restore") }
            },
            dismissButton = { TextButton(onClick = { pending = null }) { Text("Cancel") } },
            containerColor = Palette.card,
        )
    }
}
