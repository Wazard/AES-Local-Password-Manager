package app.securevault.android.core

import java.io.ByteArrayOutputStream
import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * The messages exchanged with the PC (core/phone_transfer.py is the other side):
 *
 *     kind (4) | name length (1) | sender name | payload size (4, big-endian) | payload
 *              | HMAC-SHA256(key = the code shown here, message = everything before)
 *
 * SVX1: the PC replaces this phone's vault. SVY1/SVY2/SVY3: sync — the PC
 * asks for this vault, gets it, and sends back the merged one.
 *
 * SVH1 on its own (no frame) is the PC's network probe, for when Bonjour
 * can't find this phone: it gets "HELLO <device name>" back.
 */
object TransferFrame {
    const val PUSH = "SVX1"
    const val SYNC_REQUEST = "SVY1"
    const val SYNC_VAULT = "SVY2"
    const val SYNC_MERGED = "SVY3"
    const val HELLO = "SVH1"
    const val MAX_SIZE = 16 * 1024 * 1024

    sealed class Outcome {
        /** Keep reading until the buffer holds at least this many bytes. */
        data class NeedMore(val atLeast: Int) : Outcome()
        /** The PC's probe (only where a first message is expected). */
        data object Hello : Outcome()
        /** The reason sent back to the PC: badcode, toolarge, protocol. */
        data class Rejected(val reason: String) : Outcome()
        class Accepted(val kind: String, val sender: String, val payload: ByteArray) : Outcome()
    }

    private fun startsWith(b: ByteArray, kind: String): Boolean {
        val k = kind.toByteArray(Charsets.US_ASCII)
        return b.size >= k.size && k.indices.all { b[it] == k[it] }
    }

    /** True if what has arrived so far could still become `kind`. */
    private fun couldBe(b: ByteArray, kind: String): Boolean {
        val k = kind.toByteArray(Charsets.US_ASCII)
        return b.indices.all { it < k.size && b[it] == k[it] }
    }

    fun parse(b: ByteArray, code: String, accepting: List<String>): Outcome {
        val opening = PUSH in accepting
        if (opening && startsWith(b, HELLO)) return Outcome.Hello
        if (b.size < 5) {
            val starts = if (opening) accepting + HELLO else accepting
            return if (starts.any { couldBe(b, it) }) Outcome.NeedMore(b.size + 1) else Outcome.Rejected("protocol")
        }
        val kind = accepting.firstOrNull { startsWith(b, it) } ?: return Outcome.Rejected("protocol")
        val nameLength = b[4].toInt() and 0xFF
        val sizeAt = 5 + nameLength
        if (b.size < sizeAt + 4) return Outcome.NeedMore(sizeAt + 4)
        val size = ((b[sizeAt].toLong() and 0xFF) shl 24) or ((b[sizeAt + 1].toLong() and 0xFF) shl 16) or
            ((b[sizeAt + 2].toLong() and 0xFF) shl 8) or (b[sizeAt + 3].toLong() and 0xFF)
        if (size > MAX_SIZE) return Outcome.Rejected("toolarge")
        val bodyEnd = sizeAt + 4 + size.toInt()
        if (b.size < bodyEnd + 32) return Outcome.NeedMore(bodyEnd + 32)
        if (b.size != bodyEnd + 32) return Outcome.Rejected("protocol")
        val mac = hmac(code, b, bodyEnd)
        if (!MessageDigest.isEqual(mac, b.copyOfRange(bodyEnd, b.size))) return Outcome.Rejected("badcode")
        return Outcome.Accepted(kind, String(b, 5, nameLength, Charsets.UTF_8), b.copyOfRange(sizeAt + 4, bodyEnd))
    }

    fun build(kind: String, payload: ByteArray, sender: String, code: String): ByteArray {
        val name = sender.toByteArray(Charsets.UTF_8).let { it.copyOf(minOf(it.size, 255)) }
        val body = ByteArrayOutputStream()
        body.write(kind.toByteArray(Charsets.US_ASCII))
        body.write(name.size)
        body.write(name)
        val n = payload.size
        body.write(byteArrayOf((n ushr 24).toByte(), (n ushr 16).toByte(), (n ushr 8).toByte(), n.toByte()))
        body.write(payload)
        val bytes = body.toByteArray()
        return bytes + hmac(code, bytes, bytes.size)
    }

    private fun hmac(code: String, data: ByteArray, length: Int): ByteArray {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(code.toByteArray(Charsets.US_ASCII), "HmacSHA256"))
        mac.update(data, 0, length)
        return mac.doFinal()
    }
}
