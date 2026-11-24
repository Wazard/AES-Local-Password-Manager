package app.securevault.android.ui

import android.content.Context
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import app.securevault.android.core.Json
import app.securevault.android.core.JsonValue

/**
 * Colours come from the desktop's UI/palette.json, bundled into the app at
 * build time, so re-theming the desktop re-themes the phone too.
 */
object Palette {
    private var colors: Map<String, Color> = emptyMap()

    fun load(context: Context) {
        colors = try {
            val root = context.assets.open("palette.json").use { Json.parse(it.readBytes()) } as JsonValue.Obj
            val table = root["colors"] as JsonValue.Obj
            table.fields.mapNotNull { (name, value) -> value.string?.let { hex(it) }?.let { name to it } }.toMap()
        } catch (e: Exception) {
            emptyMap()
        }
    }

    private fun hex(text: String): Color? {
        val h = text.trim().removePrefix("#")
        if (h.length != 6) return null
        val v = h.toIntOrNull(16) ?: return null
        return Color(red = (v shr 16) and 0xFF, green = (v shr 8) and 0xFF, blue = v and 0xFF)
    }

    fun color(name: String): Color = colors[name] ?: Color.Gray

    val background get() = color("bg_window")
    val bar get() = color("bg_bar")
    val card get() = color("bg_card")
    val input get() = color("bg_input")
    val border get() = color("border_subtle")
    val text get() = color("text_primary")
    val secondaryText get() = color("text_secondary")
    val muted get() = color("text_muted")
    val primary get() = color("primary")
    val primarySubtle get() = color("primary_subtle")
    val secondary get() = color("secondary")
    val danger get() = color("danger")
    val accent get() = color("accent")
    val positive get() = color("positive")
    val negative get() = color("negative")
    fun strength(score: Int) = color("strength_$score")
}

val Mono = TextStyle(fontFamily = FontFamily.Monospace)

@Composable
fun SecureVaultTheme(content: @Composable () -> Unit) {
    val scheme = darkColorScheme(
        primary = Palette.primary,
        onPrimary = Color.White,
        primaryContainer = Palette.primarySubtle,
        onPrimaryContainer = Palette.text,
        secondary = Palette.secondaryText,
        onSecondary = Palette.background,
        secondaryContainer = Palette.secondary,
        onSecondaryContainer = Palette.text,
        tertiary = Palette.accent,
        background = Palette.background,
        onBackground = Palette.text,
        surface = Palette.background,
        onSurface = Palette.text,
        surfaceVariant = Palette.input,
        onSurfaceVariant = Palette.secondaryText,
        surfaceContainerLowest = Palette.background,
        surfaceContainerLow = Palette.bar,
        surfaceContainer = Palette.card,
        surfaceContainerHigh = Palette.card,
        surfaceContainerHighest = Palette.secondary,
        outline = Palette.border,
        outlineVariant = Palette.border,
        error = Palette.negative,
        onError = Color.White,
    )
    MaterialTheme(colorScheme = scheme, content = content)
}
