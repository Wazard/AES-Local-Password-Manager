package app.securevault.android.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Fingerprint
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.withResumed
import app.securevault.android.Authenticate
import app.securevault.android.BuildConfig
import app.securevault.android.VaultStore
import app.securevault.android.core.PasswordStrength

@Composable
private fun FullScreen(content: @Composable () -> Unit) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.fillMaxSize().safeDrawingPadding().imePadding()
            .verticalScroll(rememberScrollState()).padding(24.dp),
    ) {
        content()
    }
}

/** First run, or after "use a different vault": open an existing file or make one. */
@Composable
fun SetupScreen(store: VaultStore, pickVault: () -> Unit, onReceive: () -> Unit) {
    var creating by rememberSaveable { mutableStateOf(false) }
    BackHandler(enabled = creating) { creating = false }

    FullScreen {
        Spacer(Modifier.height(48.dp))
        AppHeader(
            if (creating) "Choose a master password. It can't be recovered if you forget it."
            else "Use the same vault as your PC, or start a new one on this device."
        )
        Spacer(Modifier.height(28.dp))
        if (creating) {
            CreateForm(store, onBack = { creating = false })
        } else {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                PrimaryButton("Open an existing vault", onClick = pickVault)
                Text(
                    "Pick vault.pwmanager in the file picker — for example in OneDrive (the OneDrive app must be installed). The app edits that file in place, so changes show up on the PC too.",
                    fontSize = 13.sp, color = Palette.secondaryText,
                    modifier = Modifier.padding(bottom = 8.dp),
                )
                SecondaryButton("Get your vault from your PC over Wi-Fi", onClick = onReceive, icon = Icons.Filled.Wifi)
                if (store.files.localVaultExists) {
                    SecondaryButton("Use the vault stored on this device", onClick = { store.useLocalVault() })
                } else {
                    SecondaryButton("Create a new vault", onClick = { creating = true })
                }
            }
        }
    }
}

@Composable
private fun CreateForm(store: VaultStore, onBack: () -> Unit) {
    var password by rememberSaveable { mutableStateOf("") }
    var confirm by rememberSaveable { mutableStateOf("") }
    val focus = remember { FocusRequester() }
    val ok = PasswordStrength.evaluate(password).ok && password == confirm
    LaunchedEffect(Unit) { focus.requestFocus() }

    Column(verticalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
        PasswordField(password, { password = it }, "Master password", Modifier.focusRequester(focus))
        StrengthMeter(password)
        PasswordField(confirm, { confirm = it }, "Confirm master password", imeAction = ImeAction.Done,
            onDone = { if (ok) store.create(password) })
        if (confirm.isNotEmpty() && confirm != password) {
            Text("The passwords don't match.", fontSize = 12.sp, color = Palette.negative)
        }
        Spacer(Modifier.height(8.dp))
        PrimaryButton("Create vault", onClick = { store.create(password) }, enabled = ok, busy = store.busy)
        TextButton(onClick = onBack, modifier = Modifier.fillMaxWidth()) { Text("Back") }
    }
}

@Composable
fun UnlockScreen(store: VaultStore, authenticate: Authenticate, onReceive: () -> Unit) {
    var password by remember { mutableStateOf("") }
    var triedFingerprint by remember { mutableStateOf(false) }
    val focus = remember { FocusRequester() }
    val lifecycle = LocalLifecycleOwner.current.lifecycle

    // The fingerprint prompt straight away, once per lock screen — but only
    // with the app in front (the screen can appear while it's in the background).
    LaunchedEffect(store.fingerprintEnabled) {
        lifecycle.withResumed { }
        if (store.fingerprintEnabled && !triedFingerprint) {
            triedFingerprint = true
            store.unlockWithFingerprint(authenticate)
        } else {
            try {
                focus.requestFocus()
            } catch (e: IllegalStateException) {
                // Not laid out yet.
            }
        }
    }

    fun unlock() {
        if (password.isEmpty() || store.busy) return
        val typed = password
        password = ""
        store.unlock(typed)
    }

    FullScreen {
        Spacer(Modifier.height(48.dp))
        val location = store.location
        AppHeader(
            when {
                location == null -> ""
                location.isExternal -> "${location.name} · opened from a file"
                else -> "${location.name} · on this device"
            }
        )
        Spacer(Modifier.height(28.dp))
        Column(verticalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
            PasswordField(password, { password = it }, "Master password", Modifier.focusRequester(focus),
                imeAction = ImeAction.Go, onDone = { unlock() })
            PrimaryButton("Unlock", onClick = { unlock() }, enabled = password.isNotEmpty(), busy = store.busy)
            if (store.fingerprintEnabled) {
                SecondaryButton("Unlock with fingerprint", onClick = { store.unlockWithFingerprint(authenticate) },
                    enabled = !store.busy, icon = Icons.Filled.Fingerprint)
            }
        }
        Spacer(Modifier.height(20.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TextButton(onClick = { store.chooseAnotherVault() }) { Text("Use a different vault", fontSize = 14.sp) }
            TextButton(onClick = onReceive) { Text("Connect to PC", fontSize = 14.sp) }
        }
        Text("v${BuildConfig.VERSION_NAME}", fontSize = 11.sp, color = Palette.muted, fontWeight = FontWeight.Normal)
    }
}
