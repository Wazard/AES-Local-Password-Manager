import XCTest
@testable import SecureVault

/// The fixtures were written by the desktop app's own code
/// (ios/tools/make_fixtures.py), so these prove the two apps share one format.
final class VaultFormatTests: XCTestCase {
    private struct Expected: Decodable {
        struct E: Decodable {
            let user: String
            let pass: String
            let url: String?
            let created: Double?
            let favourite: Bool?
        }
        let password: String
        let order: [String]
        let entries: [String: E]
    }

    private func fixture(_ name: String, _ ext: String) throws -> Data {
        let url = try XCTUnwrap(Bundle(for: Self.self).url(forResource: name, withExtension: ext))
        return try Data(contentsOf: url)
    }

    private func expected() throws -> Expected {
        try JSONDecoder().decode(Expected.self, from: fixture("expected", "json"))
    }

    private func checkMatches(_ entries: [Entry], _ session: SessionCrypto, _ exp: Expected,
                              file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertEqual(entries.map(\.name), exp.order, "entry order", file: file, line: line)
        for e in entries {
            guard let x = exp.entries[e.name] else { return XCTFail("unexpected \(e.name)", file: file, line: line) }
            XCTAssertEqual(e.user, x.user, file: file, line: line)
            XCTAssertEqual(session.open(e.sealedPassword), x.pass, file: file, line: line)
            XCTAssertEqual(e.url, x.url ?? "", file: file, line: line)
            XCTAssertEqual(e.favourite, x.favourite ?? false, file: file, line: line)
            if let created = x.created {
                XCTAssertEqual(try XCTUnwrap(e.createdDate).timeIntervalSince1970, created, accuracy: 1e-6,
                               file: file, line: line)
            } else {
                XCTAssertNil(e.created, file: file, line: line)
            }
        }
    }

    func testOpensDesktopVault() throws {
        let exp = try expected()
        let opened = try VaultFormat.open(try fixture("vault_v2", "bin"), password: exp.password)
        XCTAssertFalse(opened.migrated)
        XCTAssertEqual(opened.key.params, .standard)
        let session = SessionCrypto()
        let entries = try VaultCodec.decode(try Gzip.decompress(opened.payload), session: session)
        checkMatches(entries, session, exp)
        let bank = try XCTUnwrap(entries.first { $0.name == "Bank" })
        XCTAssertEqual(bank.extra.map { $0.0 }, ["future_field"], "unknown keys are kept")
    }

    func testOpensLegacyVaultAndPlansMigration() throws {
        let exp = try expected()
        let opened = try VaultFormat.open(try fixture("vault_v1", "bin"), password: exp.password)
        XCTAssertTrue(opened.migrated)
        XCTAssertEqual(opened.key.params, .standard)
        let session = SessionCrypto()
        checkMatches(try VaultCodec.decode(try Gzip.decompress(opened.payload), session: session), session, exp)
    }

    func testWrongPasswordIsRejected() throws {
        XCTAssertThrowsError(try VaultFormat.open(try fixture("vault_v2", "bin"), password: "nope")) {
            guard case VaultError.wrongPassword = $0 else { return XCTFail("got \($0)") }
        }
    }

    /// Write with the iOS code, read back with the iOS code — and, in CI, with
    /// the desktop code too (check_roundtrip.py reads the exported file).
    func testRoundTripKeepsEverything() throws {
        let exp = try expected()
        let opened = try VaultFormat.open(try fixture("vault_v2", "bin"), password: exp.password)
        let session = SessionCrypto()
        var entries = try VaultCodec.decode(try Gzip.decompress(opened.payload), session: session)
        entries.append(Entry(name: "Added on iOS", user: "ios", url: "apple.com", favourite: false,
                             created: Entry.nowStamp(), sealedPassword: session.seal("from-the-phone")))

        let blob = try VaultFormat.seal(try Gzip.compress(VaultCodec.encode(entries, session: session)),
                                        with: opened.key)
        // Same key, so it opens without re-deriving — what a save picked up from another device relies on.
        let again = try VaultCodec.decode(try Gzip.decompress(try VaultFormat.open(blob, key: opened.key)),
                                          session: session)
        XCTAssertEqual(again.map(\.name), exp.order + ["Added on iOS"])
        XCTAssertEqual(session.open(again.last!.sealedPassword), "from-the-phone")
        XCTAssertEqual(again.first { $0.name == "Bank" }?.extra.count, 1)

        if let dir = ProcessInfo.processInfo.environment["SV_EXPORT_DIR"] {
            try blob.write(to: URL(fileURLWithPath: dir).appendingPathComponent("roundtrip.pwmanager"))
        }
    }

    func testChangedKeyIsDetected() throws {
        let exp = try expected()
        let opened = try VaultFormat.open(try fixture("vault_v2", "bin"), password: exp.password)
        let other = try VaultFormat.newKey("a different password")
        let blob = try VaultFormat.seal(try Gzip.compress(Data("{}".utf8)), with: other)
        XCTAssertThrowsError(try VaultFormat.open(blob, key: opened.key)) {
            guard case VaultError.changedElsewhere = $0 else { return XCTFail("got \($0)") }
        }
        XCTAssertTrue(VaultFormat.matches(exp.password, opened.key))
        XCTAssertFalse(VaultFormat.matches("wrong", opened.key))
    }

    func testJSONWritesLikePython() {
        let value = JSONValue.object([
            ("Café ☕ 😀", .object([("pass", .string("a\"b\\c\nd")), ("created", .number("1731000000.5"))])),
        ])
        let text = String(decoding: JSON.serialize(value), as: UTF8.self)
        XCTAssertEqual(text, #"{"Caf\u00e9 \u2615 \ud83d\ude00": {"pass": "a\"b\\c\nd", "created": 1731000000.5}}"#)
        guard case .object(let fields)? = try? JSON.parse(Data(text.utf8)) else { return XCTFail() }
        XCTAssertEqual(fields.first?.0, "Café ☕ 😀")
    }

    /// transfer_frame.bin is what the PC's "Send to iPhone" puts on the wire
    /// (core/phone_transfer.build_message), with code 123456.
    func testAcceptsTransferFromPC() throws {
        let frame = try fixture("transfer_frame", "bin")
        let vault = try fixture("vault_v2", "bin")
        XCTAssertEqual(TransferFrame.parse(frame, code: "123456"),
                       .accepted(sender: "TEST-PC \u{2615}", vault: vault))
        XCTAssertEqual(TransferFrame.parse(frame, code: "123457"), .rejected("badcode"))
        XCTAssertEqual(TransferFrame.parse(frame.prefix(40), code: "123456"), .needMore)
        XCTAssertEqual(TransferFrame.parse(frame.prefix(2), code: "123456"), .needMore)
        XCTAssertEqual(TransferFrame.parse(frame + Data([0]), code: "123456"), .rejected("protocol"))
        XCTAssertEqual(TransferFrame.parse(Data("GET / HTTP/1.1".utf8), code: "123456"), .rejected("protocol"))
        let huge = Data("SVX1".utf8) + Data([0, 0x7F, 0xFF, 0xFF, 0xFF])
        XCTAssertEqual(TransferFrame.parse(huge, code: "123456"), .rejected("toolarge"))
    }

    func testGeneratorHonoursOptions() {
        for _ in 0..<50 {
            let p = PasswordGenerator.generate(length: 20, upper: true, digits: true, symbols: false, grouped: false)
            XCTAssertEqual(p.count, 20)
            XCTAssertTrue(p.contains { $0.isUppercase })
            XCTAssertTrue(p.contains { $0.isNumber })
            XCTAssertFalse(p.contains { PasswordGenerator.symbols.contains($0) })
        }
        let grouped = PasswordGenerator.generate(length: 18, grouped: true)
        XCTAssertEqual(grouped.split(separator: "-").map(\.count), [6, 6, 6])
    }

    /// The same cases ios/tools/check_search.py runs against the desktop search.
    func testSearchMatchesDesktop() throws {
        let spec = try XCTUnwrap(JSONSerialization.jsonObject(with: fixture("search_cases", "json")) as? [String: Any])
        let rows = try XCTUnwrap(spec["entries"] as? [[Any]])
        let session = SessionCrypto()
        let entries = try rows.map { row -> Entry in
            let name = try XCTUnwrap(row[0] as? String)
            let f = try XCTUnwrap(row[1] as? [String: Any])
            return Entry(name: name, user: f["user"] as? String ?? "", url: f["url"] as? String ?? "",
                         favourite: f["favourite"] as? Bool ?? false, created: nil,
                         sealedPassword: session.seal(""))
        }
        let cases = try XCTUnwrap(spec["cases"] as? [[String: Any]])
        XCTAssertGreaterThan(cases.count, 10)
        for c in cases {
            let q = try XCTUnwrap(c["q"] as? String)
            let want = try XCTUnwrap(c["expect"] as? [String])
            XCTAssertEqual(Search.visible(entries, query: q, sort: .nameAsc).map(\.name), want, "query \(q)")
        }
    }

    func testStrengthRules() {
        XCTAssertFalse(PasswordStrength.evaluate("short1A").ok)
        XCTAssertTrue(PasswordStrength.evaluate("alllowercase").ok)
        XCTAssertEqual(PasswordStrength.evaluate("abcdefgh").score, 1)
        XCTAssertTrue(PasswordStrength.evaluate("abcdefgh1").ok)
        XCTAssertEqual(PasswordStrength.evaluate("Abcdefgh1!xyz").score, 4)
    }
}
