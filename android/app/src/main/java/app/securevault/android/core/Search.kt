package app.securevault.android.core

import java.text.Normalizer
import java.util.Locale

enum class SortMode(val raw: String, val label: String) {
    // Same identifiers as the desktop's sort modes.
    NAME_ASC("name_asc", "Name (A–Z)"),
    NAME_DESC("name_desc", "Name (Z–A)"),
    TIME_NEW("time_new", "Newest first"),
    TIME_OLD("time_old", "Oldest first");

    companion object {
        fun fromRaw(raw: String?) = entries.firstOrNull { it.raw == raw } ?: NAME_ASC
    }
}

/**
 * Contextual search, the same rules as the desktop's core/data_handler.py
 * (both are checked against ios/SecureVaultTests/Fixtures/search_cases.json):
 *
 * - every word of the query has to turn up in the name, the username or the
 *   website (any field, any order);
 * - case, accents and punctuation don't matter: "luca rossi", "lucarossi"
 *   and "LUCA.ROSSI" all find luca.rossi@…;
 * - an address can be typed loosely: "luca@outlook" finds
 *   luca.rossi@outlook.it (before @: anywhere in the mailbox name; after
 *   it: the start of the domain).
 */
object Search {
    private class Fields(val plain: List<String>, val squashed: List<String>)

    private fun fields(entry: Entry): Fields {
        val url = fold(entry.url)
        val plain = listOf(fold(entry.name), fold(entry.user), url, host(url)).filter { it.isNotEmpty() }.distinct()
        return Fields(plain, plain.map { squash(it) })
    }

    /** Port of data_handler.visible_services: sorted, filtered, favourites first. */
    fun visible(entries: List<Entry>, query: String, sort: SortMode): List<Entry> {
        var list = entries.filter { !it.isDeleted }   // file order is oldest-first
        list = when (sort) {
            SortMode.NAME_ASC -> list.sortedBy { it.name.lowercase(Locale.ROOT) }
            SortMode.NAME_DESC -> list.sortedByDescending { it.name.lowercase(Locale.ROOT) }
            SortMode.TIME_NEW -> list.reversed()
            SortMode.TIME_OLD -> list
        }
        if (query.isNotBlank()) list = list.filter { matches(it, query) }
        return list.filter { it.favourite } + list.filter { !it.favourite }
    }

    fun matches(entry: Entry, query: String): Boolean {
        val words = fold(query).split(Regex("\\s+")).filter { it.isNotEmpty() }
        if (words.isEmpty()) return true
        val f = fields(entry)
        return words.all { termMatches(it, f) }
    }

    private fun termMatches(term: String, f: Fields): Boolean {
        if (f.plain.any { it.contains(term) }) return true
        // A word that is only punctuation says nothing, so it matches.
        val bare = squash(term)
        if (bare.isEmpty() || f.squashed.any { it.contains(bare) }) return true
        if (term.count { it == '@' } == 1) {
            val name = term.substringBefore('@')
            val domain = term.substringAfter('@')
            for (field in f.plain) {
                val at = field.lastIndexOf('@')
                if (at < 0) continue
                if (field.substring(0, at).contains(name) && field.substring(at + 1).startsWith(domain)) return true
            }
        }
        return false
    }

    private val marks = Regex("\\p{M}+")

    /** Lowercase, accents dropped. */
    fun fold(text: String): String =
        Normalizer.normalize(text.lowercase(Locale.ROOT), Normalizer.Form.NFKD).replace(marks, "")

    private fun squash(text: String): String = text.filter { it.isLetterOrDigit() }

    /** "https://www.Example.com/x" -> "example.com"; bare domains work too. */
    private fun host(url: String): String {
        var u = url.trim()
        if (u.isEmpty()) return ""
        if (!u.contains("://")) u = "http://$u"
        var rest = u.substringAfter("://").takeWhile { it != '/' && it != '?' && it != '#' }
        rest = rest.substringAfterLast('@')
        rest = if (rest.startsWith("[")) rest.substringAfter('[').substringBefore(']') else rest.substringBefore(':')
        var h = rest.lowercase(Locale.ROOT)
        if (h.startsWith("www.")) h = h.substring(4)
        return h
    }
}
