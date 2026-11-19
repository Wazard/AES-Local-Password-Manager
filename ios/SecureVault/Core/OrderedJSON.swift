import Foundation

/// JSON with object keys kept in file order.
///
/// The vault's entry order is meaningful — it is what the "oldest / newest"
/// sorts use, exactly as on the desktop — and Foundation's parser returns
/// unordered dictionaries. So the vault gets its own small codec.
indirect enum JSONValue {
    case string(String)
    case number(String)   // kept as written, so a round trip never reformats it
    case bool(Bool)
    case null
    case array([JSONValue])
    case object([(String, JSONValue)])

    var stringValue: String? {
        if case .string(let s) = self { return s }
        return nil
    }

    var boolValue: Bool? {
        if case .bool(let b) = self { return b }
        return nil
    }
}

struct JSONError: Error {}

enum JSON {
    static func parse(_ data: Data) throws -> JSONValue {
        var parser = Parser(bytes: [UInt8](data))
        parser.skipSpace()
        let value = try parser.value()
        parser.skipSpace()
        guard parser.at == parser.bytes.count else { throw JSONError() }
        return value
    }

    /// Writes JSON the way Python's `json.dumps` does by default (", " and
    /// ": " separators, non-ASCII as \u escapes), so files written here look
    /// just like the ones the desktop writes.
    static func serialize(_ value: JSONValue) -> Data {
        var out = ""
        write(value, into: &out)
        return Data(out.utf8)
    }

    private static func write(_ value: JSONValue, into out: inout String) {
        switch value {
        case .string(let s): writeString(s, into: &out)
        case .number(let n): out += n
        case .bool(let b): out += b ? "true" : "false"
        case .null: out += "null"
        case .array(let items):
            out += "["
            for (i, item) in items.enumerated() {
                if i > 0 { out += ", " }
                write(item, into: &out)
            }
            out += "]"
        case .object(let fields):
            out += "{"
            for (i, (key, item)) in fields.enumerated() {
                if i > 0 { out += ", " }
                writeString(key, into: &out)
                out += ": "
                write(item, into: &out)
            }
            out += "}"
        }
    }

    private static func writeString(_ s: String, into out: inout String) {
        out += "\""
        for scalar in s.unicodeScalars {
            switch scalar {
            case "\"": out += "\\\""
            case "\\": out += "\\\\"
            case "\n": out += "\\n"
            case "\r": out += "\\r"
            case "\t": out += "\\t"
            default:
                let v = scalar.value
                if v >= 0x20 && v < 0x7F {
                    out.unicodeScalars.append(scalar)
                } else if v > 0xFFFF {
                    let u = v - 0x10000
                    out += String(format: "\\u%04x\\u%04x", 0xD800 + (u >> 10), 0xDC00 + (u & 0x3FF))
                } else {
                    out += String(format: "\\u%04x", v)
                }
            }
        }
        out += "\""
    }
}

private struct Parser {
    let bytes: [UInt8]
    var at = 0

    private static let quote = UInt8(ascii: "\"")
    private static let backslash = UInt8(ascii: "\\")

    mutating func skipSpace() {
        while at < bytes.count, [0x20, 0x09, 0x0A, 0x0D].contains(bytes[at]) { at += 1 }
    }

    private func peek() throws -> UInt8 {
        guard at < bytes.count else { throw JSONError() }
        return bytes[at]
    }

    mutating func value() throws -> JSONValue {
        switch try peek() {
        case UInt8(ascii: "{"): return try object()
        case UInt8(ascii: "["): return try array()
        case Parser.quote: return .string(try string())
        case UInt8(ascii: "t"): try literal("true"); return .bool(true)
        case UInt8(ascii: "f"): try literal("false"); return .bool(false)
        case UInt8(ascii: "n"): try literal("null"); return .null
        default: return try number()
        }
    }

    private mutating func literal(_ word: String) throws {
        let w = Array(word.utf8)
        guard at + w.count <= bytes.count, Array(bytes[at..<at + w.count]) == w else { throw JSONError() }
        at += w.count
    }

    private mutating func object() throws -> JSONValue {
        at += 1
        var fields: [(String, JSONValue)] = []
        skipSpace()
        if try peek() == UInt8(ascii: "}") { at += 1; return .object(fields) }
        while true {
            skipSpace()
            guard try peek() == Parser.quote else { throw JSONError() }
            let key = try string()
            skipSpace()
            guard try peek() == UInt8(ascii: ":") else { throw JSONError() }
            at += 1
            skipSpace()
            let item = try value()
            // Like Python: a repeated key keeps its first position, last value.
            if let i = fields.firstIndex(where: { $0.0 == key }) {
                fields[i].1 = item
            } else {
                fields.append((key, item))
            }
            skipSpace()
            switch try peek() {
            case UInt8(ascii: ","): at += 1
            case UInt8(ascii: "}"): at += 1; return .object(fields)
            default: throw JSONError()
            }
        }
    }

    private mutating func array() throws -> JSONValue {
        at += 1
        var items: [JSONValue] = []
        skipSpace()
        if try peek() == UInt8(ascii: "]") { at += 1; return .array(items) }
        while true {
            skipSpace()
            items.append(try value())
            skipSpace()
            switch try peek() {
            case UInt8(ascii: ","): at += 1
            case UInt8(ascii: "]"): at += 1; return .array(items)
            default: throw JSONError()
            }
        }
    }

    private mutating func number() throws -> JSONValue {
        let start = at
        while at < bytes.count, "+-0123456789.eE".utf8.contains(bytes[at]) { at += 1 }
        let text = String(decoding: bytes[start..<at], as: UTF8.self)
        guard !text.isEmpty, Double(text) != nil else { throw JSONError() }
        return .number(text)
    }

    private mutating func hex4() throws -> UInt32 {
        guard at + 4 <= bytes.count,
              let v = UInt32(String(decoding: bytes[at..<at + 4], as: UTF8.self), radix: 16)
        else { throw JSONError() }
        at += 4
        return v
    }

    mutating func string() throws -> String {
        at += 1
        var out: [UInt8] = []
        while at < bytes.count {
            let c = bytes[at]
            at += 1
            if c == Parser.quote { return String(decoding: out, as: UTF8.self) }
            if c != Parser.backslash { out.append(c); continue }
            let e = try peek()
            at += 1
            switch e {
            case Parser.quote: out.append(0x22)
            case Parser.backslash: out.append(0x5C)
            case UInt8(ascii: "/"): out.append(0x2F)
            case UInt8(ascii: "b"): out.append(0x08)
            case UInt8(ascii: "f"): out.append(0x0C)
            case UInt8(ascii: "n"): out.append(0x0A)
            case UInt8(ascii: "r"): out.append(0x0D)
            case UInt8(ascii: "t"): out.append(0x09)
            case UInt8(ascii: "u"):
                var v = try hex4()
                if (0xD800...0xDBFF).contains(v), at + 1 < bytes.count,
                   bytes[at] == Parser.backslash, bytes[at + 1] == UInt8(ascii: "u") {
                    let save = at
                    at += 2
                    let low = try hex4()
                    if (0xDC00...0xDFFF).contains(low) {
                        v = 0x10000 + ((v - 0xD800) << 10) + (low - 0xDC00)
                    } else {
                        at = save
                    }
                }
                var s = ""
                s.unicodeScalars.append(Unicode.Scalar(v) ?? "\u{FFFD}")
                out.append(contentsOf: Array(s.utf8))
            default:
                throw JSONError()
            }
        }
        throw JSONError()
    }
}
