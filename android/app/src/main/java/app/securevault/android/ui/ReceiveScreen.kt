package app.securevault.android.ui

import android.text.format.Formatter
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import app.securevault.android.VaultStore
import app.securevault.android.data.ReceivedVault
import app.securevault.android.data.VaultReceiver
import app.securevault.android.data.VaultReceiver.State

/**
 * "Connect to PC": listens on the Wi-Fi while open and shows the code the PC
 * must type. The PC either syncs (this vault goes to the PC, the merged one
 * comes back) or replaces this vault, which asks here first.
 */
@Composable
fun ReceiveScreen(store: VaultStore, onClose: () -> Unit) {
    val context = LocalContext.current
    val receiver = remember { VaultReceiver(context.applicationContext, store.files) }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val view = LocalView.current
    BackHandler(onBack = onClose)

    DisposableEffect(lifecycle) {
        receiver.start(store.location)
        // Not in the background: stop listening, and listen again on return.
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_STOP -> receiver.stop()
                Lifecycle.Event.ON_START -> if (receiver.state == State.Idle) receiver.start(store.location)
                else -> {}
            }
        }
        lifecycle.addObserver(observer)
        onDispose {
            lifecycle.removeObserver(observer)
            receiver.close()
        }
    }

    val state = receiver.state
    // The screen stays on while waiting, like the iPhone's.
    DisposableEffect(state == State.Waiting) {
        view.keepScreenOn = state == State.Waiting
        onDispose { view.keepScreenOn = false }
    }
    // Show the merged vault straight away if it is open here.
    LaunchedEffect(state) {
        if (state is State.Synced) store.reloadAfterSync()
    }

    Scaffold(containerColor = Palette.background, topBar = { Bar("Connect to PC", onClose) }) { padding ->
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(20.dp),
            modifier = Modifier.padding(padding).verticalScroll(rememberScrollState()).padding(24.dp),
        ) {
            when (state) {
                State.Idle, State.Waiting -> WaitingContent(receiver)
                is State.Received -> ReceivedContent(store, state.vault, onUse = onClose, onDiscard = {
                    receiver.discard()
                    onClose()
                })
                is State.Synced -> {
                    Big(Icons.Filled.Sync, Palette.positive)
                    Text("Synced with ${state.sender}", fontSize = 20.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
                    Text("Your changes are in the PC's vault, and this phone now has the same vault as the PC. The previous version is kept in the backups.",
                        color = Palette.secondaryText, textAlign = TextAlign.Center)
                    PrimaryButton("Done", onClick = onClose)
                }
                is State.Failed -> {
                    Big(Icons.Filled.Warning, Palette.negative)
                    Text(state.message, textAlign = TextAlign.Center)
                    PrimaryButton("Start again", onClick = { receiver.start(store.location) })
                }
            }
        }
    }
}

@Composable
private fun Big(icon: ImageVector, tint: Color) {
    Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(48.dp))
}

@Composable
private fun WaitingContent(receiver: VaultReceiver) {
    Big(Icons.Filled.Computer, Palette.primary)
    Text("On your PC, open Secure Vault, click the phone icon and choose Sync. Pick this phone (or type its address) and enter this code:",
        color = Palette.secondaryText, textAlign = TextAlign.Center)
    val code = receiver.code
    Surface(color = Palette.card, shape = RoundedCornerShape(12.dp)) {
        Text(if (code.length == 6) code.take(3) + " " + code.takeLast(3) else code,
            style = Mono, fontSize = 40.sp, fontWeight = FontWeight.SemiBold, color = Palette.text,
            modifier = Modifier.padding(horizontal = 24.dp, vertical = 12.dp))
    }
    val address = receiver.address
    if (address != null) {
        Surface(
            color = Palette.card, shape = RoundedCornerShape(10.dp),
            border = if (receiver.announced) null else BorderStroke(1.dp, Palette.accent),
        ) {
            Column(Modifier.padding(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                Row {
                    Text("This phone's address  ", color = Palette.secondaryText)
                    Text(address, style = Mono, fontWeight = if (receiver.announced) FontWeight.Normal else FontWeight.Bold)
                }
                if (!receiver.announced) {
                    Text("Android didn't let this phone announce itself. The PC should still find it by its address; if it doesn't, type this address on the PC.",
                        fontSize = 13.sp, color = Palette.accent, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 8.dp))
                }
            }
        }
    } else {
        Text("Connect to the same Wi-Fi network as the PC.", color = Palette.negative, textAlign = TextAlign.Center)
    }
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp, color = Palette.secondaryText)
        Text("Waiting for the PC…", color = Palette.secondaryText)
    }
    Text("Keep this screen open. If the PC can't connect, check that both are on the same Wi-Fi and that a VPN on either side allows local network traffic.",
        fontSize = 13.sp, color = Palette.muted, textAlign = TextAlign.Center)
}

@Composable
private fun ReceivedContent(store: VaultStore, vault: ReceivedVault, onUse: () -> Unit, onDiscard: () -> Unit) {
    val context = LocalContext.current
    Big(Icons.Filled.CheckCircle, Palette.positive)
    Text("Vault received from ${vault.sender}", fontSize = 20.sp, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
    Text(Formatter.formatShortFileSize(context, vault.data.size.toLong()), color = Palette.secondaryText)
    val note = buildList {
        add("It opens with the master password it has on the PC.")
        if (store.files.localVaultExists) add("It replaces the vault stored on this phone, which is kept as a backup.")
        store.location?.takeIf { it.isExternal }?.let { add("The app will use this copy instead of ${it.name}.") }
    }.joinToString(" ")
    Text(note, color = Palette.secondaryText, textAlign = TextAlign.Center, fontSize = 15.sp)
    PrimaryButton("Use this vault", busy = store.busy, onClick = { store.installReceived(vault, onUse) })
    SecondaryButton("Discard", onClick = onDiscard, modifier = Modifier.fillMaxWidth())
}
