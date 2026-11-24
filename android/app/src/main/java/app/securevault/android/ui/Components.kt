@file:OptIn(ExperimentalMaterial3Api::class)

package app.securevault.android.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.securevault.android.core.PasswordStrength

private val Rounded = RoundedCornerShape(10.dp)

@Composable
fun PrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    busy: Boolean = false,
    icon: ImageVector? = null,
) {
    Button(
        onClick = onClick,
        enabled = enabled && !busy,
        shape = Rounded,
        colors = ButtonDefaults.buttonColors(
            containerColor = Palette.primary, contentColor = Color.White,
            disabledContainerColor = Palette.muted, disabledContentColor = Color.White.copy(alpha = 0.7f),
        ),
        modifier = modifier.fillMaxWidth().heightIn(min = 48.dp),
    ) {
        if (busy) {
            CircularProgressIndicator(Modifier.size(20.dp), color = Color.White, strokeWidth = 2.dp)
        } else {
            ButtonLabel(text, icon)
        }
    }
}

@Composable
fun SecondaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    icon: ImageVector? = null,
) {
    Button(
        onClick = onClick,
        enabled = enabled,
        shape = Rounded,
        colors = ButtonDefaults.buttonColors(
            containerColor = Palette.secondary, contentColor = Palette.text,
            disabledContainerColor = Palette.secondary, disabledContentColor = Palette.muted,
        ),
        modifier = modifier.fillMaxWidth().heightIn(min = 48.dp),
    ) {
        ButtonLabel(text, icon)
    }
}

@Composable
private fun ButtonLabel(text: String, icon: ImageVector?) {
    if (icon != null) {
        Icon(icon, contentDescription = null, modifier = Modifier.size(20.dp))
        Spacer(Modifier.width(8.dp))
    }
    Text(text, fontWeight = FontWeight.SemiBold, fontSize = 16.sp)
}

@Composable
fun AppHeader(subtitle: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth()) {
        Icon(Icons.Filled.Lock, contentDescription = null, tint = Palette.primary, modifier = Modifier.size(56.dp))
        Spacer(Modifier.height(10.dp))
        Text("Secure Vault", fontSize = 32.sp, fontWeight = FontWeight.Bold, color = Palette.text)
        Spacer(Modifier.height(10.dp))
        Text(subtitle, color = Palette.secondaryText, textAlign = TextAlign.Center, fontSize = 15.sp)
    }
}

@Composable
fun fieldColors() = OutlinedTextFieldDefaults.colors(
    focusedContainerColor = Palette.input,
    unfocusedContainerColor = Palette.input,
    focusedBorderColor = Palette.primary,
    unfocusedBorderColor = Palette.border,
    focusedTextColor = Palette.text,
    unfocusedTextColor = Palette.text,
    focusedLabelColor = Palette.primary,
    unfocusedLabelColor = Palette.secondaryText,
    cursorColor = Palette.primary,
)

/** A password field with a show/hide eye. */
@Composable
fun PasswordField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    imeAction: ImeAction = ImeAction.Next,
    onDone: () -> Unit = {},
) {
    var shown by rememberSaveable { mutableStateOf(false) }
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = { Text(label) },
        singleLine = true,
        textStyle = if (shown) Mono else androidx.compose.ui.text.TextStyle.Default,
        visualTransformation = if (shown) VisualTransformation.None else PasswordVisualTransformation(),
        keyboardOptions = KeyboardOptions(
            keyboardType = KeyboardType.Password, autoCorrectEnabled = false, imeAction = imeAction,
        ),
        keyboardActions = KeyboardActions(onDone = { onDone() }, onGo = { onDone() }),
        trailingIcon = {
            IconButton(onClick = { shown = !shown }) {
                Icon(
                    if (shown) Icons.Filled.VisibilityOff else Icons.Filled.Visibility,
                    contentDescription = if (shown) "Hide password" else "Show password",
                    tint = Palette.secondaryText,
                )
            }
        },
        colors = fieldColors(),
        shape = Rounded,
        modifier = modifier.fillMaxWidth(),
    )
}

/** The four-step bar used wherever a master password is chosen. */
@Composable
fun StrengthMeter(password: String) {
    val result = PasswordStrength.evaluate(password)
    Column(Modifier.fillMaxWidth()) {
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp), modifier = Modifier.fillMaxWidth()) {
            for (i in 0 until 4) {
                val lit = password.isNotEmpty() && i < maxOf(result.score, 1)
                Box(
                    Modifier.weight(1f).height(4.dp)
                        .background(if (lit) Palette.strength(result.score) else Palette.color("track"), RoundedCornerShape(2.dp))
                )
            }
        }
        Spacer(Modifier.height(6.dp))
        Text(
            if (password.isEmpty()) "At least 8 characters, and at least “Fair”." else PasswordStrength.labels[result.score],
            fontSize = 12.sp,
            color = if (password.isEmpty()) Palette.muted else Palette.strength(result.score),
        )
    }
}

/** A titled group of rows on a card, with an optional explanation under it. */
@Composable
fun Section(title: String?, footer: String? = null, content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxWidth().padding(bottom = 20.dp)) {
        if (title != null) {
            Text(title.uppercase(), fontSize = 12.sp, color = Palette.secondaryText, fontWeight = FontWeight.Medium,
                modifier = Modifier.padding(start = 16.dp, bottom = 6.dp))
        }
        Surface(color = Palette.card, shape = Rounded, border = BorderStroke(1.dp, Palette.border)) {
            Column(Modifier.fillMaxWidth(), content = content)
        }
        if (footer != null) {
            Text(footer, fontSize = 13.sp, color = Palette.secondaryText,
                modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 6.dp))
        }
    }
}

/** One tappable row inside a [Section]. */
@Composable
fun SectionRow(
    title: String,
    value: String? = null,
    color: Color = Palette.text,
    onClick: (() -> Unit)? = null,
    trailing: @Composable (() -> Unit)? = null,
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.fillMaxWidth()
            .let { if (onClick != null) it.clickable(onClick = onClick) else it }
            .heightIn(min = 52.dp)
            .padding(horizontal = 16.dp, vertical = 8.dp),
    ) {
        Text(title, color = color, modifier = Modifier.weight(1f), fontSize = 16.sp)
        if (value != null) Text(value, color = Palette.secondaryText, fontSize = 15.sp, textAlign = TextAlign.End)
        trailing?.invoke()
    }
}

@Composable
fun barColors() = TopAppBarDefaults.topAppBarColors(
    containerColor = Palette.bar,
    scrolledContainerColor = Palette.bar,
    titleContentColor = Palette.text,
    navigationIconContentColor = Palette.text,
    actionIconContentColor = Palette.text,
)

@Composable
fun Bar(title: String, onBack: (() -> Unit)?, actions: @Composable () -> Unit = {}) {
    TopAppBar(
        title = { Text(title, maxLines = 1) },
        navigationIcon = {
            if (onBack != null) {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                }
            }
        },
        actions = { actions() },
        colors = barColors(),
    )
}

/** The short confirmation at the bottom of the screen ("Password copied"). */
@Composable
fun ToastHost(message: String?) {
    // Keep the last text while the pill slides away.
    val last = remember { mutableStateOf("") }
    if (message != null) last.value = message
    Box(Modifier.fillMaxSize().navigationBarsPadding().padding(bottom = 24.dp), contentAlignment = Alignment.BottomCenter) {
        AnimatedVisibility(
            visible = message != null,
            enter = slideInVertically { it } + fadeIn(),
            exit = slideOutVertically { it } + fadeOut(),
        ) {
            Surface(color = Palette.card, shape = RoundedCornerShape(50), border = BorderStroke(1.dp, Palette.border)) {
                Text(last.value, color = Palette.text, fontWeight = FontWeight.Medium, fontSize = 15.sp,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp))
            }
        }
    }
}

val ScreenPadding = PaddingValues(horizontal = 16.dp, vertical = 16.dp)
