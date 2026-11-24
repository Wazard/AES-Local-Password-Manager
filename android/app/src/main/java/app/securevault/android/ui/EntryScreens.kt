@file:OptIn(ExperimentalMaterial3Api::class)

package app.securevault.android.ui

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.StarBorder
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import app.securevault.android.VaultStore
import java.text.DateFormat
import java.util.Date

@Composable
fun EntryDetailScreen(store: VaultStore, id: String, onBack: () -> Unit, edit: () -> Unit) {
    val entry = store.entry(id)
    var revealed by remember { mutableStateOf<String?>(null) }
    var confirmDelete by remember { mutableStateOf(false) }
    val context = LocalContext.current
    DisposableEffect(Unit) { onDispose { revealed = null } }

    Scaffold(
        containerColor = Palette.background,
        topBar = {
            Bar(entry?.name ?: "", onBack) {
                if (entry != null) {
                    IconButton(onClick = { store.toggleFavourite(entry.name) }) {
                        Icon(
                            if (entry.favourite) Icons.Filled.Star else Icons.Filled.StarBorder,
                            contentDescription = if (entry.favourite) "Remove from favourites" else "Add to favourites",
                            tint = if (entry.favourite) Palette.accent else Palette.secondaryText,
                        )
                    }
                    IconButton(onClick = {
                        revealed = null
                        edit()
                    }) { Icon(Icons.Filled.Edit, contentDescription = "Edit") }
                }
            }
        },
    ) { padding ->
        if (entry == null) {
            Box(Modifier.padding(padding).fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("This account no longer exists.", color = Palette.secondaryText)
            }
            return@Scaffold
        }
        Column(Modifier.padding(padding).verticalScroll(rememberScrollState()).padding(16.dp)) {
            Section("Username") {
                SectionRow(entry.user.ifEmpty { "—" }, trailing = {
                    CopyButton { store.copy(entry.user, "Username") }
                })
            }
            Section("Password") {
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(start = 16.dp)) {
                    SelectionContainer(Modifier.weight(1f)) {
                        Text(revealed ?: "••••••••••", style = Mono, fontSize = 16.sp)
                    }
                    IconButton(onClick = { revealed = if (revealed == null) store.password(entry) else null }) {
                        Icon(
                            if (revealed == null) Icons.Filled.Visibility else Icons.Filled.VisibilityOff,
                            contentDescription = if (revealed == null) "Show password" else "Hide password",
                            tint = Palette.secondaryText,
                        )
                    }
                    CopyButton { store.copy(store.password(entry), "Password") }
                }
            }
            Section("Website") {
                val link = linkFor(entry.url)
                if (link != null) {
                    Text(entry.url, color = Palette.primary, textDecoration = TextDecoration.Underline, fontSize = 16.sp,
                        modifier = Modifier.fillMaxWidth().clickable {
                            try {
                                context.startActivity(Intent(Intent.ACTION_VIEW, link))
                            } catch (e: ActivityNotFoundException) {
                                store.showToast("No app can open this address")
                            }
                        }.padding(16.dp))
                } else {
                    SectionRow("No website", color = Palette.muted)
                }
            }
            entry.createdMillis?.let { millis ->
                Section(null) {
                    SectionRow("Added", DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT).format(Date(millis)))
                }
            }
            Section(null) {
                SectionRow("Delete account", color = Palette.negative, onClick = { confirmDelete = true })
            }
        }
    }

    if (confirmDelete && entry != null) {
        ConfirmDelete(entry.name, onConfirm = {
            confirmDelete = false
            store.delete(entry.name) { ok -> if (ok) onBack() }
        }, onDismiss = { confirmDelete = false })
    }
}

@Composable
private fun CopyButton(onClick: () -> Unit) {
    IconButton(onClick = onClick) {
        Icon(Icons.Filled.ContentCopy, contentDescription = "Copy", tint = Palette.secondaryText)
    }
}

private fun linkFor(url: String): Uri? {
    val u = url.trim()
    if (u.isEmpty()) return null
    return Uri.parse(if (u.contains("://")) u else "https://$u")
}

/**
 * Add or edit. When editing, the stored password isn't decrypted unless the
 * user asks to change it — same rule as the desktop's edit form.
 */
@Composable
fun EntryFormScreen(store: VaultStore, editingId: String?, onClose: () -> Unit) {
    val editing = remember(editingId) { editingId?.let { store.entry(it) } }
    var name by rememberSaveable { mutableStateOf(editing?.name ?: "") }
    var user by rememberSaveable { mutableStateOf(editing?.user ?: "") }
    var url by rememberSaveable { mutableStateOf(editing?.url ?: "") }
    /** null while editing and the password wasn't asked for. */
    var password by remember { mutableStateOf(if (editing == null) "" else null) }
    var generating by remember { mutableStateOf(false) }
    var problem by remember { mutableStateOf<String?>(null) }
    var saving by remember { mutableStateOf(false) }
    var confirmDiscard by remember { mutableStateOf(false) }
    val dirty = editing == null && (name.isNotEmpty() || user.isNotEmpty() || !password.isNullOrEmpty())

    // Don't lose a half-typed new account to a stray back gesture.
    BackHandler(enabled = dirty) { confirmDiscard = true }

    fun save() {
        if (saving) return
        saving = true
        problem = null
        store.saveEntry(editing?.name, name, user, url, password) { result ->
            saving = false
            if (result == null) onClose() else problem = result
        }
    }

    Scaffold(
        containerColor = Palette.background,
        topBar = {
            TopAppBar(
                title = { Text(if (editing == null) "New account" else "Edit account") },
                navigationIcon = {
                    IconButton(onClick = { if (dirty) confirmDiscard = true else onClose() }) {
                        Icon(Icons.Filled.Close, contentDescription = "Cancel")
                    }
                },
                actions = {
                    TextButton(onClick = { save() }, enabled = !saving) {
                        Text("Save", fontWeight = FontWeight.SemiBold)
                    }
                },
                colors = barColors(),
            )
        },
    ) { padding ->
        Column(
            verticalArrangement = Arrangement.spacedBy(12.dp),
            modifier = Modifier.padding(padding).imePadding().verticalScroll(rememberScrollState()).padding(16.dp),
        ) {
            OutlinedTextField(
                value = name, onValueChange = { name = it }, label = { Text("Account name") }, singleLine = true,
                keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Words),
                colors = fieldColors(), shape = RoundedCornerShape(10.dp), modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = user, onValueChange = { user = it }, label = { Text("Username or email") }, singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, autoCorrectEnabled = false),
                colors = fieldColors(), shape = RoundedCornerShape(10.dp), modifier = Modifier.fillMaxWidth(),
            )
            val current = password
            if (current != null) {
                PasswordField(current, { password = it }, "Password")
                TextButton(onClick = { generating = true }) {
                    Icon(Icons.Filled.AutoAwesome, contentDescription = null)
                    Text("  Generate a password")
                }
            } else {
                Section(null) {
                    SectionRow("••••••••••", color = Palette.secondaryText, trailing = {
                        TextButton(onClick = { editing?.let { password = store.password(it) } }) { Text("Change") }
                    })
                }
            }
            OutlinedTextField(
                value = url, onValueChange = { url = it }, label = { Text("Website (example.com)") }, singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, autoCorrectEnabled = false),
                colors = fieldColors(), shape = RoundedCornerShape(10.dp), modifier = Modifier.fillMaxWidth(),
            )
            problem?.let { Text(it, color = Palette.negative) }
        }
    }

    if (generating) {
        Dialog(onDismissRequest = { generating = false }, properties = DialogProperties(usePlatformDefaultWidth = false)) {
            GeneratorScreen(store, onUse = {
                password = it
                generating = false
            }, onClose = { generating = false })
        }
    }
    if (confirmDiscard) {
        AlertDialog(
            onDismissRequest = { confirmDiscard = false },
            title = { Text("Discard this account?") },
            confirmButton = { TextButton(onClick = { confirmDiscard = false; onClose() }) { Text("Discard", color = Palette.negative) } },
            dismissButton = { TextButton(onClick = { confirmDiscard = false }) { Text("Keep editing") } },
            containerColor = Palette.card,
        )
    }
}
