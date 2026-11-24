@file:OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)

package app.securevault.android.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Key
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.securevault.android.VaultStore
import app.securevault.android.core.Entry
import app.securevault.android.core.SortMode

@Composable
fun AccountsScreen(
    store: VaultStore,
    open: (String) -> Unit,
    add: () -> Unit,
    settings: () -> Unit,
    generator: () -> Unit,
) {
    var query by rememberSaveable { mutableStateOf("") }
    var menu by remember { mutableStateOf(false) }
    var pendingDelete by remember { mutableStateOf<Entry?>(null) }
    val visible = remember(store.entries, query, store.sort) { store.visible(query) }

    Scaffold(
        containerColor = Palette.background,
        topBar = {
            TopAppBar(
                title = { Text("Accounts") },
                navigationIcon = {
                    IconButton(onClick = { store.lock() }) { Icon(Icons.Filled.Lock, contentDescription = "Lock") }
                },
                actions = {
                    IconButton(onClick = { menu = true }) { Icon(Icons.Filled.MoreVert, contentDescription = "More") }
                    DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                        Text("Sort", fontSize = 12.sp, color = Palette.secondaryText,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp))
                        for (mode in SortMode.entries) {
                            DropdownMenuItem(
                                text = { Text(mode.label) },
                                leadingIcon = {
                                    if (store.sort == mode) Icon(Icons.Filled.Check, contentDescription = null)
                                    else Spacer(Modifier.size(24.dp))
                                },
                                onClick = {
                                    store.updateSort(mode)
                                    menu = false
                                },
                            )
                        }
                        HorizontalDivider()
                        DropdownMenuItem(
                            text = { Text("Password generator") },
                            leadingIcon = { Icon(Icons.Filled.AutoAwesome, contentDescription = null) },
                            onClick = {
                                menu = false
                                generator()
                            },
                        )
                        DropdownMenuItem(
                            text = { Text("Settings") },
                            leadingIcon = { Icon(Icons.Filled.Settings, contentDescription = null) },
                            onClick = {
                                menu = false
                                settings()
                            },
                        )
                    }
                },
                colors = barColors(),
            )
        },
        floatingActionButton = {
            FloatingActionButton(onClick = add, containerColor = Palette.primary, contentColor = Color.White) {
                Icon(Icons.Filled.Add, contentDescription = "Add account")
            }
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                placeholder = { Text("Search accounts") },
                leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null, tint = Palette.secondaryText) },
                trailingIcon = {
                    if (query.isNotEmpty()) {
                        IconButton(onClick = { query = "" }) { Icon(Icons.Filled.Close, contentDescription = "Clear search") }
                    }
                },
                singleLine = true,
                keyboardOptions = KeyboardOptions(autoCorrectEnabled = false, imeAction = ImeAction.Search),
                colors = fieldColors(),
                shape = RoundedCornerShape(10.dp),
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
            )
            if (visible.isEmpty()) {
                EmptyState(query, add)
            } else {
                LazyColumn(
                    contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 4.dp, bottom = 96.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(visible, key = { it.id }) { entry ->
                        EntryRow(
                            entry,
                            onClick = { open(entry.id) },
                            onCopyUser = { store.copy(entry.user, "Username") },
                            onCopyPassword = { store.copy(store.password(entry), "Password") },
                            onFavourite = { store.toggleFavourite(entry.name) },
                            onDelete = { pendingDelete = entry },
                        )
                    }
                }
            }
        }
    }

    pendingDelete?.let { entry ->
        ConfirmDelete(entry.name, onConfirm = {
            pendingDelete = null
            store.delete(entry.name)
        }, onDismiss = { pendingDelete = null })
    }
}

@Composable
fun ConfirmDelete(name: String, onConfirm: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Delete $name?") },
        text = { Text("This removes the account from the vault on every device that uses it.") },
        confirmButton = { TextButton(onClick = onConfirm) { Text("Delete", color = Palette.negative) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
        containerColor = Palette.card,
    )
}

@Composable
private fun EmptyState(query: String, add: () -> Unit) {
    Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
        if (query.isEmpty()) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(Icons.Filled.Key, contentDescription = null, tint = Palette.muted, modifier = Modifier.size(40.dp))
                Spacer(Modifier.height(12.dp))
                Text("No accounts yet", fontWeight = FontWeight.SemiBold, fontSize = 17.sp)
                TextButton(onClick = add) { Text("Add your first account") }
            }
        } else {
            Text("No accounts match “$query”.", color = Palette.secondaryText)
        }
    }
}

/** One account in the list. Tap opens it; a long press offers copy, favourite and delete. */
@Composable
private fun EntryRow(
    entry: Entry,
    onClick: () -> Unit,
    onCopyUser: () -> Unit,
    onCopyPassword: () -> Unit,
    onFavourite: () -> Unit,
    onDelete: () -> Unit,
) {
    var menu by remember { mutableStateOf(false) }
    Box {
        Surface(color = Palette.card, shape = RoundedCornerShape(10.dp),
            modifier = Modifier.fillMaxWidth().combinedClickable(onClick = onClick, onLongClick = { menu = true })) {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(start = 12.dp, top = 10.dp, bottom = 10.dp, end = 4.dp)) {
                Box(
                    Modifier.size(36.dp).background(Palette.primarySubtle, RoundedCornerShape(8.dp)),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(entry.name.take(1).uppercase(), color = Palette.primary, fontWeight = FontWeight.Bold, fontSize = 17.sp)
                }
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(entry.name, fontWeight = FontWeight.Medium, fontSize = 16.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    val subtitle = entry.user.ifEmpty { entry.url }
                    if (subtitle.isNotEmpty()) {
                        Text(subtitle, fontSize = 13.sp, color = Palette.secondaryText, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                }
                if (entry.favourite) {
                    Icon(Icons.Filled.Star, contentDescription = "Favourite", tint = Palette.accent, modifier = Modifier.size(16.dp))
                }
                IconButton(onClick = onCopyPassword) {
                    Icon(Icons.Filled.Key, contentDescription = "Copy password", tint = Palette.secondaryText)
                }
            }
        }
        DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
            DropdownMenuItem(text = { Text("Copy username") }, onClick = { menu = false; onCopyUser() })
            DropdownMenuItem(text = { Text("Copy password") }, onClick = { menu = false; onCopyPassword() })
            DropdownMenuItem(
                text = { Text(if (entry.favourite) "Remove from favourites" else "Add to favourites") },
                onClick = { menu = false; onFavourite() },
            )
            DropdownMenuItem(text = { Text("Delete", color = Palette.negative) }, onClick = { menu = false; onDelete() })
        }
    }
}
