package app.securevault.android.ui

import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import app.securevault.android.Authenticate
import app.securevault.android.Phase
import app.securevault.android.VaultStore

/** Screens of the unlocked app, as a simple back stack. */
sealed interface Route {
    data object Accounts : Route
    data class Detail(val id: String) : Route
    data class Form(val editingId: String?) : Route
    data object Generator : Route
    data object Settings : Route
    data object ChangeMaster : Route
    data object Backups : Route
}

@Composable
fun Root(store: VaultStore, authenticate: Authenticate) {
    var receiving by rememberSaveable { mutableStateOf(false) }
    // Registered here, where it is always on screen: picking a file leaves the
    // app, which may lock it and close the screen that asked.
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) store.adopt(uri)
    }
    val pickVault = { picker.launch(arrayOf("*/*")) }
    Box(Modifier.fillMaxSize().background(Palette.background)) {
        if (receiving) {
            ReceiveScreen(store, onClose = { receiving = false })
        } else {
            when (store.phase) {
                Phase.SETUP -> SetupScreen(store, pickVault, onReceive = { receiving = true })
                Phase.LOCKED -> UnlockScreen(store, authenticate, onReceive = { receiving = true })
                Phase.UNLOCKED -> UnlockedApp(store, authenticate, pickVault, onReceive = { receiving = true })
            }
        }
        ToastHost(store.toast)
        store.error?.let { message ->
            AlertDialog(
                onDismissRequest = { store.error = null },
                confirmButton = { TextButton(onClick = { store.error = null }) { Text("OK") } },
                title = { Text("Secure Vault") },
                text = { Text(message) },
                containerColor = Palette.card,
            )
        }
    }
}

@Composable
private fun UnlockedApp(store: VaultStore, authenticate: Authenticate, pickVault: () -> Unit, onReceive: () -> Unit) {
    var stack by remember { mutableStateOf(listOf<Route>(Route.Accounts)) }
    val push: (Route) -> Unit = { stack = stack + it }
    val pop: () -> Unit = { if (stack.size > 1) stack = stack.dropLast(1) }
    BackHandler(enabled = stack.size > 1, onBack = pop)
    // An account that went away (deleted, or gone after a sync) closes its screens.
    LaunchedEffect(store.entries) {
        stack = stack.filter { route ->
            when (route) {
                is Route.Detail -> store.entry(route.id) != null
                is Route.Form -> route.editingId == null || store.entry(route.editingId) != null
                else -> true
            }
        }
    }

    when (val top = stack.last()) {
        Route.Accounts -> AccountsScreen(
            store,
            open = { push(Route.Detail(it)) },
            add = { push(Route.Form(null)) },
            settings = { push(Route.Settings) },
            generator = { push(Route.Generator) },
        )
        is Route.Detail -> EntryDetailScreen(store, top.id, onBack = pop, edit = { push(Route.Form(top.id)) })
        is Route.Form -> EntryFormScreen(store, top.editingId, onClose = pop)
        Route.Generator -> GeneratorScreen(store, onUse = null, onClose = pop)
        Route.Settings -> SettingsScreen(
            store, authenticate, pickVault,
            onBack = pop,
            onReceive = onReceive,
            changeMaster = { push(Route.ChangeMaster) },
            backups = { push(Route.Backups) },
        )
        Route.ChangeMaster -> ChangeMasterScreen(store, onBack = pop)
        Route.Backups -> BackupsScreen(store, onBack = pop)
    }
}
