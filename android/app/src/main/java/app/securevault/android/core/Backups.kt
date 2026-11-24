package app.securevault.android.core

import java.io.File
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.util.Locale

class BackupFile(val file: File, val date: LocalDateTime, val size: Long)

/**
 * Dated copies of every saved state, with the same names and retention rules
 * as the desktop's core/backup.py: vault_bk_2026_08_08_1432_01.pwmanager; the
 * newest 20 are kept, plus the last one of each day for 60 days.
 */
class Backups(val dir: File) {
    private val keepRecent = 20
    private val keepDays = 60L
    private val stamp = DateTimeFormatter.ofPattern("yyyy_MM_dd_HHmm", Locale.ROOT)

    /** Never throws — a failed backup must not turn a good save into a bad one. */
    fun make(blob: ByteArray) {
        try {
            dir.mkdirs()
            val base = "vault_bk_" + LocalDateTime.now().format(stamp) + "_"
            for (index in 1..99) {
                val file = File(dir, base + String.format(Locale.ROOT, "%02d", index) + ".pwmanager")
                if (!file.exists()) {
                    file.writeBytes(blob)
                    break
                }
            }
            prune()
        } catch (e: Exception) {
            // Best effort.
        }
    }

    /** Newest first (the names sort chronologically). */
    fun list(): List<BackupFile> {
        val names = dir.list()?.sortedDescending() ?: return emptyList()
        return names.mapNotNull { name ->
            if (!name.startsWith("vault_bk_") || !name.endsWith(".pwmanager") || name.length != 37) return@mapNotNull null
            val date = try {
                LocalDateTime.parse(name.substring(9, 24), stamp)
            } catch (e: DateTimeParseException) {
                return@mapNotNull null
            }
            val file = File(dir, name)
            BackupFile(file, date, file.length())
        }
    }

    fun read(backup: BackupFile): ByteArray {
        val blob = backup.file.readBytes()
        if (!VaultFormat.looksLikeVault(blob)) throw VaultError.NotAVault()
        return blob
    }

    private fun prune() {
        val backups = list()
        val keep = backups.take(keepRecent).map { it.file }.toMutableSet()
        val cutoff = LocalDateTime.now(ZoneId.systemDefault()).minusDays(keepDays)
        val days = mutableSetOf<java.time.LocalDate>()
        for (b in backups) {
            if (b.date >= cutoff && days.add(b.date.toLocalDate())) keep.add(b.file)
        }
        for (b in backups) if (b.file !in keep) b.file.delete()
    }
}
