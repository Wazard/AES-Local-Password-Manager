import Foundation

/// Ports of `core/password_generator.py` and `core/password_strength.py`.
enum PasswordGenerator {
    static let lowercase = Array("abcdefghijklmnopqrstuvwxyz")
    static let uppercase = Array("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    static let digits = Array("0123456789")
    static let symbols = Array("!@#$%^&*()-_=+[]{};:,.?")
    static let groupSize = 6

    /// Lowercase is always in; each enabled class appears at least once.
    /// `SystemRandomNumberGenerator` is the system CSPRNG on Apple platforms.
    static func generate(length: Int = 18, upper: Bool = true, digits useDigits: Bool = true,
                         symbols useSymbols: Bool = true, grouped: Bool = true) -> String {
        var rng = SystemRandomNumberGenerator()
        var charset = lowercase
        var chars = [lowercase.randomElement(using: &rng)!]
        for (on, set) in [(upper, uppercase), (useDigits, digits), (useSymbols, symbols)] where on {
            charset += set
            chars.append(set.randomElement(using: &rng)!)
        }
        let length = max(length, chars.count, 8)
        while chars.count < length { chars.append(charset.randomElement(using: &rng)!) }
        chars.shuffle(using: &rng)

        let password = String(chars)
        guard grouped else { return password }
        return stride(from: 0, to: chars.count, by: groupSize)
            .map { String(chars[$0..<min($0 + groupSize, chars.count)]) }
            .joined(separator: "-")
    }
}

enum PasswordStrength {
    static let labels = ["Very weak", "Weak", "Fair", "Good", "Strong"]

    /// Score 0–4. `ok` is the minimum for a new master password
    /// (at least 8 characters and "fair"), same rule as the desktop.
    static func evaluate(_ password: String) -> (score: Int, ok: Bool) {
        let classes = [
            password.contains { $0.isASCII && $0.isLowercase },
            password.contains { $0.isASCII && $0.isUppercase },
            password.contains { $0.isASCII && $0.isNumber },
            password.contains { !($0.isASCII && ($0.isLetter || $0.isNumber)) },
        ].filter { $0 }.count
        let n = password.count
        var score = 0
        if n >= 8 { score += 1 }
        if n >= 12 { score += 1 }
        if classes >= 2 { score += 1 }
        if classes >= 3 && n >= 10 { score += 1 }
        score = min(score, 4)
        return (score, n >= 8 && score >= 2)
    }
}
