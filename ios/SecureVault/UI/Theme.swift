import SwiftUI

/// Colours come from the desktop's UI/palette.json, bundled into the app, so
/// re-theming the desktop re-themes the phone too.
enum Theme {
    private static let colors: [String: Color] = {
        guard let url = Bundle.main.url(forResource: "palette", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let colors = json["colors"] as? [String: String]
        else { return [:] }
        return colors.compactMapValues(Color.init(hex:))
    }()

    static func color(_ name: String) -> Color { colors[name] ?? .gray }

    static var background: Color { color("bg_window") }
    static var bar: Color { color("bg_bar") }
    static var card: Color { color("bg_card") }
    static var input: Color { color("bg_input") }
    static var border: Color { color("border_subtle") }
    static var text: Color { color("text_primary") }
    static var secondaryText: Color { color("text_secondary") }
    static var muted: Color { color("text_muted") }
    static var primary: Color { color("primary") }
    static var primarySubtle: Color { color("primary_subtle") }
    static var danger: Color { color("danger") }
    static var accent: Color { color("accent") }
    static var positive: Color { color("positive") }
    static var negative: Color { color("negative") }
    static func strength(_ score: Int) -> Color { color("strength_\(score)") }

    static let mono = Font.system(.body, design: .monospaced)
}

extension Color {
    init?(hex: String) {
        let h = hex.trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        guard h.count == 6, let v = UInt32(h, radix: 16) else { return nil }
        self.init(red: Double(v >> 16 & 0xFF) / 255,
                  green: Double(v >> 8 & 0xFF) / 255,
                  blue: Double(v & 0xFF) / 255)
    }
}

/// Lists and forms on the palette background instead of system grey.
struct Themed: ViewModifier {
    func body(content: Content) -> some View {
        content
            .scrollContentBackground(.hidden)
            .background(Theme.background.ignoresSafeArea())
            .toolbarBackground(Theme.bar, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
    }
}

extension View {
    func themed() -> some View { modifier(Themed()) }
    func cardRow() -> some View { listRowBackground(Theme.card) }
}

struct PrimaryButton: ButtonStyle {
    var color: Color = Theme.primary
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .frame(maxWidth: .infinity, minHeight: 48)
            .foregroundStyle(.white)
            .background(color.opacity(configuration.isPressed ? 0.8 : 1),
                        in: RoundedRectangle(cornerRadius: 10))
    }
}

struct SecondaryButton: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.headline)
            .frame(maxWidth: .infinity, minHeight: 48)
            .foregroundStyle(Theme.text)
            .background(Theme.color(configuration.isPressed ? "secondary_hover" : "secondary"),
                        in: RoundedRectangle(cornerRadius: 10))
    }
}

/// The five-step bar used wherever a master password is chosen.
struct StrengthMeter: View {
    let password: String

    var body: some View {
        let result = PasswordStrength.evaluate(password)
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 4) {
                ForEach(0..<4) { i in
                    Capsule()
                        .fill(!password.isEmpty && i < max(result.score, 1)
                              ? Theme.strength(result.score) : Theme.color("track"))
                        .frame(height: 4)
                }
            }
            Text(password.isEmpty ? "At least 8 characters, and at least “Fair”."
                                  : PasswordStrength.labels[result.score])
                .font(.caption)
                .foregroundStyle(password.isEmpty ? Theme.muted : Theme.strength(result.score))
        }
    }
}

/// A password field with a show/hide eye.
struct RevealableField: View {
    let title: String
    @Binding var text: String
    @State private var shown = false

    var body: some View {
        HStack {
            Group {
                if shown {
                    TextField(title, text: $text).font(Theme.mono)
                } else {
                    SecureField(title, text: $text)
                }
            }
            .textInputAutocapitalization(.never)
            .autocorrectionDisabled()
            Button { shown.toggle() } label: {
                Image(systemName: shown ? "eye.slash" : "eye").foregroundStyle(Theme.secondaryText)
            }
            .buttonStyle(.borderless)
            .accessibilityLabel(shown ? "Hide password" : "Show password")
        }
    }
}
