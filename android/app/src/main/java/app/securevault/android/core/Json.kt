package app.securevault.android.core

import java.io.ByteArrayOutputStream
import java.util.Locale

/**
 * JSON with object keys kept in file order.
 *
 * The vault's entry order is meaningful — it is what the "oldest / newest"
 * sorts use, exactly as on the desktop — and numbers are kept as written, so
 * a round trip never reformats a timestamp. Same codec as the iOS app's
 * OrderedJSON.swift.
 */
sealed class JsonValue {
    data class Str(val value: String) : JsonValue()
    data class Num(val text: String) : JsonValue()
    data class Bool(val value: Boolean) : JsonValue()
    data object Null : JsonValue()
    data class Arr(val items: List<JsonValue>) : JsonValue()
    data class Obj(val fields: List<Pair<String, JsonValue>>) : JsonValue() {
        operator fun get(key: String): JsonValue? = fields.firstOrNull { it.first == key }?.second
    }

    val string: String? get() = (this as? Str)?.value
    val bool: Boolean? get() = (this as? Bool)?.value
}

class JsonException : Exception("Invalid JSON")

object Json {
    fun parse(data: ByteArray): JsonValue {
        val parser = Parser(data)
        parser.skipSpace()
        val value = parser.value()
        parser.skipSpace()
        if (parser.at != data.size) throw JsonException()
        return value
    }

    /**
     * Writes JSON the way Python's `json.dumps` does by default (", " and
     * ": " separators, non-ASCII as \u escapes), so files written here look
     * just like the ones the desktop writes.
     */
    fun serialize(value: JsonValue): ByteArray {
        val out = StringBuilder()
        write(value, out)
        return out.toString().toByteArray(Charsets.UTF_8)
    }

    private fun write(value: JsonValue, out: StringBuilder) {
        when (value) {
            is JsonValue.Str -> writeString(value.value, out)
            is JsonValue.Num -> out.append(value.text)
            is JsonValue.Bool -> out.append(if (value.value) "true" else "false")
            is JsonValue.Null -> out.append("null")
            is JsonValue.Arr -> {
                out.append('[')
                value.items.forEachIndexed { i, item ->
                    if (i > 0) out.append(", ")
                    write(item, out)
                }
                out.append(']')
            }
            is JsonValue.Obj -> {
                out.append('{')
                value.fields.forEachIndexed { i, (key, item) ->
                    if (i > 0) out.append(", ")
                    writeString(key, out)
                    out.append(": ")
                    write(item, out)
                }
                out.append('}')
            }
        }
    }

    private fun writeString(s: String, out: StringBuilder) {
        out.append('"')
        // Kotlin strings are UTF-16, so characters outside the BMP come out as
        // a surrogate pair of escapes — exactly what Python writes.
        for (c in s) {
            when (c) {
                '"' -> out.append("\\\"")
                '\\' -> out.append("\\\\")
                '\n' -> out.append("\\n")
                '\r' -> out.append("\\r")
                '\t' -> out.append("\\t")
                '\b' -> out.append("\\b")
                '\u000C' -> out.append("\\f")
                else -> if (c.code in 0x20..0x7E) out.append(c)
                else out.append(String.format(Locale.ROOT, "\\u%04x", c.code))
            }
        }
        out.append('"')
    }
}

private class Parser(private val bytes: ByteArray) {
    var at = 0

    fun skipSpace() {
        while (at < bytes.size) {
            val c = bytes[at].toInt()
            if (c != 0x20 && c != 0x09 && c != 0x0A && c != 0x0D) return
            at++
        }
    }

    private fun peek(): Int {
        if (at >= bytes.size) throw JsonException()
        return bytes[at].toInt() and 0xFF
    }

    fun value(): JsonValue = when (peek().toChar()) {
        '{' -> obj()
        '[' -> arr()
        '"' -> JsonValue.Str(string())
        't' -> { literal("true"); JsonValue.Bool(true) }
        'f' -> { literal("false"); JsonValue.Bool(false) }
        'n' -> { literal("null"); JsonValue.Null }
        else -> number()
    }

    private fun literal(word: String) {
        val w = word.toByteArray(Charsets.US_ASCII)
        if (at + w.size > bytes.size) throw JsonException()
        for (i in w.indices) if (bytes[at + i] != w[i]) throw JsonException()
        at += w.size
    }

    private fun obj(): JsonValue {
        at++
        val fields = ArrayList<Pair<String, JsonValue>>()
        skipSpace()
        if (peek() == '}'.code) {
            at++
            return JsonValue.Obj(fields)
        }
        while (true) {
            skipSpace()
            if (peek() != '"'.code) throw JsonException()
            val key = string()
            skipSpace()
            if (peek() != ':'.code) throw JsonException()
            at++
            skipSpace()
            val item = value()
            // Like Python: a repeated key keeps its first position, last value.
            val i = fields.indexOfFirst { it.first == key }
            if (i >= 0) fields[i] = key to item else fields.add(key to item)
            skipSpace()
            when (peek()) {
                ','.code -> at++
                '}'.code -> {
                    at++
                    return JsonValue.Obj(fields)
                }
                else -> throw JsonException()
            }
        }
    }

    private fun arr(): JsonValue {
        at++
        val items = ArrayList<JsonValue>()
        skipSpace()
        if (peek() == ']'.code) {
            at++
            return JsonValue.Arr(items)
        }
        while (true) {
            skipSpace()
            items.add(value())
            skipSpace()
            when (peek()) {
                ','.code -> at++
                ']'.code -> {
                    at++
                    return JsonValue.Arr(items)
                }
                else -> throw JsonException()
            }
        }
    }

    private fun number(): JsonValue {
        val start = at
        while (at < bytes.size && (bytes[at].toInt().toChar() in "+-0123456789.eE")) at++
        val text = String(bytes, start, at - start, Charsets.US_ASCII)
        if (text.isEmpty() || text.toDoubleOrNull() == null) throw JsonException()
        return JsonValue.Num(text)
    }

    private fun hex4(): Int {
        if (at + 4 > bytes.size) throw JsonException()
        val text = String(bytes, at, 4, Charsets.US_ASCII)
        if (!text.all { it in '0'..'9' || it in 'a'..'f' || it in 'A'..'F' }) throw JsonException()
        at += 4
        return text.toInt(16)
    }

    fun string(): String {
        at++
        val out = ByteArrayOutputStream()
        while (at < bytes.size) {
            val c = bytes[at].toInt() and 0xFF
            at++
            if (c == '"'.code) return out.toString("UTF-8")
            if (c != '\\'.code) {
                out.write(c)
                continue
            }
            val e = peek()
            at++
            when (e.toChar()) {
                '"' -> out.write(0x22)
                '\\' -> out.write(0x5C)
                '/' -> out.write(0x2F)
                'b' -> out.write(0x08)
                'f' -> out.write(0x0C)
                'n' -> out.write(0x0A)
                'r' -> out.write(0x0D)
                't' -> out.write(0x09)
                'u' -> {
                    var v = hex4()
                    if (v in 0xD800..0xDBFF && at + 1 < bytes.size &&
                        bytes[at] == '\\'.code.toByte() && bytes[at + 1] == 'u'.code.toByte()
                    ) {
                        val save = at
                        at += 2
                        val low = hex4()
                        if (low in 0xDC00..0xDFFF) {
                            v = 0x10000 + ((v - 0xD800) shl 10) + (low - 0xDC00)
                        } else {
                            at = save
                        }
                    }
                    val codePoint = if (v in 0xD800..0xDFFF) 0xFFFD else v
                    out.write(String(Character.toChars(codePoint)).toByteArray(Charsets.UTF_8))
                }
                else -> throw JsonException()
            }
        }
        throw JsonException()
    }
}
