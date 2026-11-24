@file:OptIn(ExperimentalMaterial3Api::class)

package app.securevault.android.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.securevault.android.VaultStore
import app.securevault.android.core.PasswordGenerator
import kotlin.math.roundToInt

/** `onUse` is set when opened from the account form: "Use" hands the password back. */
@Composable
fun GeneratorScreen(store: VaultStore, onUse: ((String) -> Unit)?, onClose: () -> Unit) {
    var length by remember { mutableFloatStateOf(store.generatorLength.toFloat()) }
    var upper by remember { mutableStateOf(store.generatorOption("upper", true)) }
    var digits by remember { mutableStateOf(store.generatorOption("digits", true)) }
    var symbols by remember { mutableStateOf(store.generatorOption("symbols", true)) }
    var grouped by remember { mutableStateOf(store.generatorOption("grouped", true)) }
    var password by remember { mutableStateOf("") }
    var generation by remember { mutableStateOf(0) }

    LaunchedEffect(length.roundToInt(), upper, digits, symbols, grouped, generation) {
        password = PasswordGenerator.generate(length.roundToInt(), upper, digits, symbols, grouped)
        store.generatorLength = length.roundToInt()
        store.setGeneratorOption("upper", upper)
        store.setGeneratorOption("digits", digits)
        store.setGeneratorOption("symbols", symbols)
        store.setGeneratorOption("grouped", grouped)
    }

    Scaffold(
        containerColor = Palette.background,
        topBar = {
            Bar("Generator", onBack = onClose) {
                if (onUse != null) {
                    TextButton(onClick = { onUse(password) }) { Text("Use", fontWeight = FontWeight.SemiBold) }
                }
            }
        },
        modifier = Modifier.fillMaxSize(),
    ) { padding ->
        Column(Modifier.padding(padding).verticalScroll(rememberScrollState()).padding(16.dp)) {
            Section(null) {
                SelectionContainer {
                    Text(password, style = Mono, fontSize = 20.sp, textAlign = TextAlign.Center,
                        modifier = Modifier.fillMaxWidth().heightIn(min = 64.dp).padding(16.dp))
                }
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.padding(start = 16.dp, end = 16.dp, bottom = 16.dp)) {
                    SecondaryButton("New", onClick = { generation++ }, icon = Icons.Filled.Refresh, modifier = Modifier.weight(1f))
                    SecondaryButton("Copy", onClick = { store.copy(password, "Password") }, icon = Icons.Filled.ContentCopy,
                        modifier = Modifier.weight(1f))
                }
            }
            Section("Options") {
                Column(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                    Text("Length: ${length.roundToInt()}", fontSize = 16.sp)
                    Slider(
                        value = length, onValueChange = { length = it }, valueRange = 8f..64f, steps = 55,
                        colors = SliderDefaults.colors(thumbColor = Palette.primary, activeTrackColor = Palette.primary),
                    )
                }
                ToggleRow("Uppercase letters", upper) { upper = it }
                ToggleRow("Digits", digits) { digits = it }
                ToggleRow("Symbols", symbols) { symbols = it }
                ToggleRow("Group in blocks of 6", grouped) { grouped = it }
            }
        }
    }
}

@Composable
fun ToggleRow(title: String, checked: Boolean, enabled: Boolean = true, onChange: (Boolean) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp)) {
        Text(title, fontSize = 16.sp, modifier = Modifier.weight(1f), color = if (enabled) Palette.text else Palette.muted)
        Switch(
            checked = checked, onCheckedChange = onChange, enabled = enabled,
            colors = SwitchDefaults.colors(checkedTrackColor = Palette.primary, checkedThumbColor = Color.White),
        )
    }
}
