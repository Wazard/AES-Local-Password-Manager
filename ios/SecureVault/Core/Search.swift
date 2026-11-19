import Foundation

/// Contextual search, the same rules as the desktop's core/data_handler.py
/// (both are checked against SecureVaultTests/Fixtures/search_cases.json):
///
/// - every word of the query has to turn up in the name, the username or the
///   website (any field, any order);
/// - case, accents and punctuation don't matter: "luca rossi", "lucarossi"
///   and "LUCA.ROSSI" all find luca.rossi@…;
/// - an address can be typed loosely: "luca@outlook" finds
///   luca.rossi@outlook.it (before @: anywhere in the mailbox name; after
///   it: the start of the domain).
enum Search {
    struct Fields {
        let plain: [String]
        let squashed: [String]
    }

    static func fields(_ entry: Entry) -> Fields {
        let url = fold(entry.url)
        var plain: [String] = []
        for f in [fold(entry.name), fold(entry.user), url, host(url)] where !f.isEmpty && !plain.contains(f) {
            plain.append(f)
        }
        return Fields(plain: plain, squashed: plain.map(squash))
    }

    /// Port of data_handler.visible_services: sorted, filtered, favourites first.
    static func visible(_ entries: [Entry], query: String, sort: SortMode) -> [Entry] {
        var list = entries   // file order is oldest-first
        switch sort {
        case .nameAsc: list.sort { $0.name.lowercased() < $1.name.lowercased() }
        case .nameDesc: list.sort { $0.name.lowercased() > $1.name.lowercased() }
        case .timeNew: list.reverse()
        case .timeOld: break
        }
        if !query.trimmingCharacters(in: .whitespaces).isEmpty {
            list = list.filter { matches($0, query) }
        }
        return list.filter(\.favourite) + list.filter { !$0.favourite }
    }

    static func matches(_ entry: Entry, _ query: String) -> Bool {
        let words = fold(query).split(whereSeparator: \.isWhitespace).map(String.init)
        guard !words.isEmpty else { return true }
        let f = fields(entry)
        return words.allSatisfy { termMatches($0, f) }
    }

    private static func termMatches(_ term: String, _ f: Fields) -> Bool {
        if f.plain.contains(where: { $0.contains(term) }) { return true }
        // A word that is only punctuation says nothing, so it matches.
        let bare = squash(term)
        if bare.isEmpty || f.squashed.contains(where: { $0.contains(bare) }) { return true }
        if term.filter({ $0 == "@" }).count == 1 {
            let parts = term.split(separator: "@", omittingEmptySubsequences: false)
            let name = String(parts[0]), domain = String(parts[1])
            for field in f.plain {
                guard let at = field.range(of: "@", options: .backwards) else { continue }
                let fieldName = field[..<at.lowerBound], fieldDomain = field[at.upperBound...]
                if (name.isEmpty || fieldName.contains(name)) && fieldDomain.hasPrefix(domain) { return true }
            }
        }
        return false
    }

    /// Lowercase, accents dropped.
    static func fold(_ text: String) -> String {
        text.folding(options: [.caseInsensitive, .diacriticInsensitive], locale: nil).lowercased()
    }

    private static func squash(_ text: String) -> String {
        String(String.UnicodeScalarView(text.unicodeScalars.filter { CharacterSet.alphanumerics.contains($0) }))
    }

    /// "https://www.Example.com/x" -> "example.com"; bare domains work too.
    private static func host(_ url: String) -> String {
        let u = url.trimmingCharacters(in: .whitespaces)
        guard !u.isEmpty, let parsed = URL(string: u.contains("://") ? u : "http://" + u),
              var h = parsed.host?.lowercased() else { return "" }
        if h.hasPrefix("www.") { h.removeFirst(4) }
        return h
    }
}
