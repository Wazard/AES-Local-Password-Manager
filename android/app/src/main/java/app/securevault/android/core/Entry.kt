package app.securevault.android.core

import java.security.GeneralSecurityException
import java.security.SecureRandom
import java.util.Locale
import java.util.UUID

/**
 * One account. The password is never kept as plaintext: it is sealed with a
 * key made fresh at every unlock and opened only when it is shown, copied or
 * saved — the same idea as the desktop's `SessionCrypto`.
 */
data class Entry(
    val name: String,
    val user: String,
    val url: String,
    val favourite: Boolean,
    /** As stored: a float on new entries, an int on some, absent on legacy ones. */
    val created: JsonValue?,
    val sealedPassword: ByteArray,
    /** Keys this version doesn't know about, written back untouched. */
    val extra: List<Pair<String, JsonValue>> = emptyList(),
    /** Not yet synced to the PC: "new", "changed" or "deleted" (see
     *  data_handler.merge_phone_changes). Stored in the vault as "sync_pending". */
    val syncState: String? = null,
    /** The name the PC knows this entry by, if it was renamed here. */
    val renamedFrom: String? = null,
    /** Stable for this unlock only; the name is the real key in the file. */
    val id: String = UUID.randomUUID().toString(),
) {
    /** Deleted here but kept until the PC has heard about it. */
    val isDeleted: Boolean get() = syncState == "deleted"

    /** Records a change for the next sync. Something created here and never
     *  synced stays "new" whatever happens to it afterwards. */
    fun markedChanged(): Entry = if (syncState == "new") this else copy(syncState = "changed")

    val createdMillis: Long?
        get() = (created as? JsonValue.Num)?.text?.toDoubleOrNull()?.let { (it * 1000).toLong() }

    companion object {
        fun nowStamp(): JsonValue =
            JsonValue.Num(String.format(Locale.ROOT, "%.6f", System.currentTimeMillis() / 1000.0))
    }
}

class SessionCrypto {
    private val key = ByteArray(32).also { SecureRandom().nextBytes(it) }

    fun seal(plaintext: String): ByteArray = Aead.seal(key, plaintext.toByteArray(Charsets.UTF_8))

    fun open(sealed: ByteArray): String {
        if (sealed.isEmpty()) return ""
        return try {
            String(Aead.open(key, sealed), Charsets.UTF_8)
        } catch (e: GeneralSecurityException) {
            ""
        }
    }
}

/** JSON payload <-> entries, in file order. */
object VaultCodec {
    private val known = setOf("user", "pass", "url", "created", "favourite", "sync_pending", "sync_renamed_from")

    fun decode(json: ByteArray, session: SessionCrypto): List<Entry> {
        val root = try {
            Json.parse(json)
        } catch (e: JsonException) {
            throw VaultError.Damaged()
        }
        val services = (root as? JsonValue.Obj) ?: throw VaultError.Damaged()
        return services.fields.map { (name, value) ->
            val fields = (value as? JsonValue.Obj)?.fields ?: emptyList()
            fun field(key: String) = fields.firstOrNull { it.first == key }?.second
            var syncState = field("sync_pending")?.string
            if (syncState == null && field("sync_pending")?.bool == true) syncState = "changed"
            Entry(
                name = name,
                user = field("user")?.string ?: "",
                url = field("url")?.string ?: "",
                favourite = field("favourite")?.bool ?: false,
                created = field("created"),
                sealedPassword = session.seal(field("pass")?.string ?: ""),
                extra = fields.filter { it.first !in known },
                syncState = syncState,
                renamedFrom = field("sync_renamed_from")?.string,
            )
        }
    }

    /** The plaintext exists only inside the returned bytes, which the caller
     *  compresses and encrypts straight away. */
    fun encode(entries: List<Entry>, session: SessionCrypto): ByteArray {
        val services = entries.map { e ->
            val fields = mutableListOf<Pair<String, JsonValue>>(
                "user" to JsonValue.Str(e.user),
                "pass" to JsonValue.Str(session.open(e.sealedPassword)),
                "url" to JsonValue.Str(e.url),
            )
            e.created?.let { fields.add("created" to it) }
            fields.add("favourite" to JsonValue.Bool(e.favourite))
            e.syncState?.let { fields.add("sync_pending" to JsonValue.Str(it)) }
            e.renamedFrom?.let { fields.add("sync_renamed_from" to JsonValue.Str(it)) }
            e.name to JsonValue.Obj(fields + e.extra)
        }
        return Json.serialize(JsonValue.Obj(services))
    }

    fun seal(entries: List<Entry>, session: SessionCrypto, key: VaultKey): ByteArray =
        VaultFormat.seal(Gzip.compress(encode(entries, session)), key)

    fun open(payload: ByteArray, session: SessionCrypto): List<Entry> =
        decode(Gzip.decompress(payload), session)
}
