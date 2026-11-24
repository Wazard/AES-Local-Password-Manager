package app.securevault.android.core

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File

/**
 * The fixtures were written by the desktop app's own code
 * (ios/tools/make_fixtures.py) and are shared with the iOS tests, so these
 * prove the Android app reads and writes the same format. CI then checks the
 * files exported here with the desktop code (ios/tools/check_*.py).
 */
class VaultFormatTest {
    private val fixtures = File(System.getProperty("sv.fixtures") ?: "../../ios/SecureVaultTests/Fixtures")
    private fun fixture(name: String) = File(fixtures, name).readBytes()

    private val expected by lazy { Json.parse(fixture("expected.json")) as JsonValue.Obj }
    private val password by lazy { expected["password"]!!.string!! }
    private val order by lazy { (expected["order"] as JsonValue.Arr).items.map { it.string!! } }
    private fun expectedEntry(name: String) = (expected["entries"] as JsonValue.Obj)[name] as JsonValue.Obj?

    private fun export(name: String, data: ByteArray) {
        val dir = System.getProperty("sv.export")?.takeIf { it.isNotEmpty() } ?: return
        File(dir).mkdirs()
        File(dir, name).writeBytes(data)
    }

    private fun checkMatches(entries: List<Entry>, session: SessionCrypto) {
        assertEquals("entry order", order, entries.map { it.name })
        for (e in entries) {
            val x = expectedEntry(e.name) ?: return fail("unexpected ${e.name}")
            assertEquals(x["user"]!!.string, e.user)
            assertEquals(x["pass"]!!.string, session.open(e.sealedPassword))
            assertEquals(x["url"]?.string ?: "", e.url)
            assertEquals(x["favourite"]?.bool ?: false, e.favourite)
            val created = (x["created"] as JsonValue.Num?)?.text?.toDouble()
            if (created != null) {
                assertEquals(created, (e.created as JsonValue.Num).text.toDouble(), 1e-6)
            } else {
                assertNull(e.created)
            }
        }
    }

    @Test
    fun opensDesktopVault() {
        val opened = VaultFormat.open(fixture("vault_v2.bin"), password)
        assertFalse(opened.migrated)
        assertEquals(KdfParams.STANDARD, opened.key.params)
        val session = SessionCrypto()
        val entries = VaultCodec.open(opened.payload, session)
        checkMatches(entries, session)
        assertEquals("unknown keys are kept", listOf("future_field"), entries.first { it.name == "Bank" }.extra.map { it.first })
    }

    @Test
    fun opensLegacyVaultAndPlansMigration() {
        val opened = VaultFormat.open(fixture("vault_v1.bin"), password)
        assertTrue(opened.migrated)
        assertEquals(KdfParams.STANDARD, opened.key.params)
        val session = SessionCrypto()
        checkMatches(VaultCodec.open(opened.payload, session), session)
    }

    @Test
    fun wrongPasswordIsRejected() {
        try {
            VaultFormat.open(fixture("vault_v2.bin"), "nope")
            fail("opened with the wrong password")
        } catch (e: VaultError.WrongPassword) {
            // Expected.
        }
    }

    /** Written here, read back here — and, in CI, by the desktop code too. */
    @Test
    fun roundTripKeepsEverything() {
        val opened = VaultFormat.open(fixture("vault_v2.bin"), password)
        val session = SessionCrypto()
        val entries = VaultCodec.open(opened.payload, session) + Entry(
            name = ADDED, user = "android", url = "android.com", favourite = false,
            created = Entry.nowStamp(), sealedPassword = session.seal("from-the-phone"),
        )
        val blob = VaultCodec.seal(entries, session, opened.key)
        // Same key, so it opens without re-deriving — what picking up another device's save relies on.
        val again = VaultCodec.open(VaultFormat.open(blob, opened.key), session)
        assertEquals(order + ADDED, again.map { it.name })
        assertEquals("from-the-phone", session.open(again.last().sealedPassword))
        assertEquals(1, again.first { it.name == "Bank" }.extra.size)
        export("roundtrip.pwmanager", blob)
    }

    @Test
    fun changedKeyIsDetected() {
        val opened = VaultFormat.open(fixture("vault_v2.bin"), password)
        val other = VaultFormat.newKey("a different password")
        val blob = VaultFormat.seal(Gzip.compress("{}".toByteArray()), other)
        try {
            VaultFormat.open(blob, opened.key)
            fail("opened a vault keyed differently")
        } catch (e: VaultError.ChangedElsewhere) {
            // Expected.
        }
        assertTrue(VaultFormat.matches(password, opened.key))
        assertFalse(VaultFormat.matches("wrong", opened.key))
    }

    @Test
    fun jsonWritesLikePython() {
        val value = JsonValue.Obj(listOf(
            "Café ☕ 😀" to JsonValue.Obj(listOf(
                "pass" to JsonValue.Str("a\"b\\c\nd"),
                "created" to JsonValue.Num("1731000000.5"),
            )),
        ))
        val text = String(Json.serialize(value), Charsets.UTF_8)
        assertEquals("""{"Caf\u00e9 \u2615 \ud83d\ude00": {"pass": "a\"b\\c\nd", "created": 1731000000.5}}""", text)
        val parsed = Json.parse(text.toByteArray()) as JsonValue.Obj
        assertEquals("Café ☕ 😀", parsed.fields.first().first)
    }

    /** transfer_frame.bin is what the PC's "Replace phone vault" puts on the
     *  wire (core/phone_transfer.build_message), with code 123456. */
    @Test
    fun acceptsTransferFromPC() {
        val kinds = listOf(TransferFrame.PUSH, TransferFrame.SYNC_REQUEST)
        val frame = fixture("transfer_frame.bin")
        val vault = fixture("vault_v2.bin")
        val accepted = TransferFrame.parse(frame, "123456", kinds) as TransferFrame.Outcome.Accepted
        assertEquals("SVX1", accepted.kind)
        assertEquals("TEST-PC ☕", accepted.sender)
        assertArrayEquals(vault, accepted.payload)
        assertEquals(TransferFrame.Outcome.Rejected("badcode"), TransferFrame.parse(frame, "123457", kinds))
        assertTrue(TransferFrame.parse(frame.copyOf(40), "123456", kinds) is TransferFrame.Outcome.NeedMore)
        assertTrue(TransferFrame.parse(frame.copyOf(2), "123456", kinds) is TransferFrame.Outcome.NeedMore)
        assertEquals(TransferFrame.Outcome.Rejected("protocol"), TransferFrame.parse(frame + byteArrayOf(0), "123456", kinds))
        assertEquals(TransferFrame.Outcome.Rejected("protocol"),
            TransferFrame.parse("GET / HTTP/1.1".toByteArray(), "123456", kinds))
        // The PC's network probe, whole or split across reads; only as an opening message.
        assertEquals(TransferFrame.Outcome.Hello, TransferFrame.parse("SVH1".toByteArray(), "123456", kinds))
        assertEquals(TransferFrame.Outcome.NeedMore(4), TransferFrame.parse("SVH".toByteArray(), "123456", kinds))
        assertEquals(TransferFrame.Outcome.Rejected("protocol"),
            TransferFrame.parse("SVH1".toByteArray(), "123456", listOf(TransferFrame.SYNC_MERGED)))
        val huge = "SVX1".toByteArray() + byteArrayOf(0, 0x7F, 0xFF.toByte(), 0xFF.toByte(), 0xFF.toByte())
        assertEquals(TransferFrame.Outcome.Rejected("toolarge"), TransferFrame.parse(huge, "123456", kinds))
    }

    /** sync_request.bin is the PC's "send me your vault" (code 123456). The
     *  reply built here is checked by ios/tools/check_sync.py with the desktop code. */
    @Test
    fun syncMessages() {
        val request = fixture("sync_request.bin")
        val accepted = TransferFrame.parse(request, "123456",
            listOf(TransferFrame.PUSH, TransferFrame.SYNC_REQUEST)) as TransferFrame.Outcome.Accepted
        assertEquals("SVY1", accepted.kind)
        assertEquals("TEST-PC", accepted.sender)
        assertEquals(0, accepted.payload.size)
        // Out of turn: only the merged vault is expected after the reply.
        assertEquals(TransferFrame.Outcome.Rejected("protocol"),
            TransferFrame.parse(request, "123456", listOf(TransferFrame.SYNC_MERGED)))

        val vault = fixture("vault_v2.bin")
        val reply = TransferFrame.build(TransferFrame.SYNC_VAULT, vault, SENDER, "123456")
        val back = TransferFrame.parse(reply, "123456", listOf(TransferFrame.SYNC_VAULT)) as TransferFrame.Outcome.Accepted
        assertEquals("SVY2", back.kind)
        assertEquals(SENDER, back.sender)
        assertArrayEquals(vault, back.payload)
        export("sync_reply.bin", reply)
    }

    /** A vault with every kind of change marked; check_sync.py merges it into
     *  the fixture vault with the desktop code and checks the result. */
    @Test
    fun syncMarks() {
        val opened = VaultFormat.open(fixture("vault_v2.bin"), password)
        val session = SessionCrypto()
        val entries = VaultCodec.open(opened.payload, session).toMutableList()
        fun index(name: String) = entries.indexOfFirst { it.name == name }.also { assertTrue(name, it >= 0) }

        val github = index("GitHub")
        entries[github] = entries[github].copy(user = "octo-new").markedChanged()
        val legacy = index("Legacy")
        entries[legacy] = entries[legacy].copy(name = "Legacy Renamed", renamedFrom = "Legacy").markedChanged()
        val bank = index("Bank")
        entries[bank] = entries[bank].copy(syncState = "deleted")
        entries.add(Entry(
            name = ADDED, user = "android", url = "android.com", favourite = true,
            created = Entry.nowStamp(), sealedPassword = session.seal("new-pw"), syncState = "new",
        ))

        val blob = VaultCodec.seal(entries, session, opened.key)
        val again = VaultCodec.open(VaultFormat.open(blob, opened.key), session)
        assertEquals("changed", again.first { it.name == "GitHub" }.syncState)
        assertEquals("Legacy", again.first { it.name == "Legacy Renamed" }.renamedFrom)
        assertTrue(again.first { it.name == "Bank" }.isDeleted)
        assertEquals("unknown keys still kept", 1, again.first { it.name == "Bank" }.extra.size)
        assertFalse("deleted accounts are hidden",
            Search.visible(again, "", SortMode.NAME_ASC).any { it.name == "Bank" })
        assertEquals("an unsynced new account stays new when edited", "new", again.last().markedChanged().syncState)
        export("sync_phone_vault.pwmanager", blob)
    }

    @Test
    fun generatorHonoursOptions() {
        repeat(50) {
            val p = PasswordGenerator.generate(length = 20, upper = true, digits = true, symbols = false, grouped = false)
            assertEquals(20, p.length)
            assertTrue(p.any { it.isUpperCase() })
            assertTrue(p.any { it.isDigit() })
            assertFalse(p.any { it in PasswordGenerator.SYMBOLS })
        }
        // "-" is also one of the symbols, so check where the separators sit
        // rather than splitting on it.
        repeat(50) {
            val grouped = PasswordGenerator.generate(length = 18, grouped = true)
            assertEquals(20, grouped.length)
            assertEquals('-', grouped[6])
            assertEquals('-', grouped[13])
        }
    }

    /** The same cases ios/tools/check_search.py runs against the desktop search. */
    @Test
    fun searchMatchesDesktop() {
        val spec = Json.parse(fixture("search_cases.json")) as JsonValue.Obj
        val session = SessionCrypto()
        val entries = (spec["entries"] as JsonValue.Arr).items.map { row ->
            val items = (row as JsonValue.Arr).items
            val f = items[1] as JsonValue.Obj
            Entry(name = items[0].string!!, user = f["user"]?.string ?: "", url = f["url"]?.string ?: "",
                favourite = f["favourite"]?.bool ?: false, created = null, sealedPassword = session.seal(""))
        }
        val cases = (spec["cases"] as JsonValue.Arr).items
        assertTrue(cases.size > 10)
        for (c in cases) {
            val case = c as JsonValue.Obj
            val q = case["q"]!!.string!!
            val want = (case["expect"] as JsonValue.Arr).items.map { it.string!! }
            assertEquals("query \"$q\"", want, Search.visible(entries, q, SortMode.NAME_ASC).map { it.name })
        }
    }

    @Test
    fun strengthRules() {
        assertFalse(PasswordStrength.evaluate("short1A").ok)
        assertTrue(PasswordStrength.evaluate("alllowercase").ok)
        assertEquals(1, PasswordStrength.evaluate("abcdefgh").score)
        assertTrue(PasswordStrength.evaluate("abcdefgh1").ok)
        assertEquals(4, PasswordStrength.evaluate("Abcdefgh1!xyz").score)
    }

    @Test
    fun backupsKeepTheDesktopNames() {
        val dir = java.nio.file.Files.createTempDirectory("sv-backups").toFile()
        val backups = Backups(dir)
        backups.make(fixture("vault_v2.bin"))
        backups.make(fixture("vault_v2.bin"))
        val list = backups.list()
        assertEquals(2, list.size)
        assertTrue(list.all { Regex("""vault_bk_\d{4}_\d\d_\d\d_\d{4}_\d\d\.pwmanager""").matches(it.file.name) })
        assertArrayEquals(fixture("vault_v2.bin"), backups.read(list.first()))
        dir.deleteRecursively()
    }

    private companion object {
        // Names the desktop-side checks are told to expect (see .github/workflows/android.yml).
        const val ADDED = "Added on Android"
        const val SENDER = "Test Android"
    }
}
