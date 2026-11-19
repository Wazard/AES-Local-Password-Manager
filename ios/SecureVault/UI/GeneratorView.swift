import SwiftUI

struct GeneratorView: View {
    @EnvironmentObject private var store: VaultStore
    @Environment(\.dismiss) private var dismiss
    /// Set when opened from the account form: "Use" hands the password back.
    let onUse: ((String) -> Void)?

    @AppStorage("gen.length") private var length = 18.0
    @AppStorage("gen.upper") private var upper = true
    @AppStorage("gen.digits") private var digits = true
    @AppStorage("gen.symbols") private var symbols = true
    @AppStorage("gen.grouped") private var grouped = true
    @State private var password = ""

    var body: some View {
        Form {
            Section {
                Text(password)
                    .font(.system(.title3, design: .monospaced))
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, minHeight: 64)
                    .multilineTextAlignment(.center)
                HStack(spacing: 12) {
                    Button { regenerate() } label: { Label("New", systemImage: "arrow.clockwise") }
                        .buttonStyle(SecondaryButton())
                    Button { store.copy(password, label: "Password") } label: {
                        Label("Copy", systemImage: "doc.on.doc")
                    }
                    .buttonStyle(SecondaryButton())
                }
                .listRowInsets(EdgeInsets(top: 8, leading: 16, bottom: 12, trailing: 16))
            }
            .cardRow()
            Section("Options") {
                VStack(alignment: .leading) {
                    Text("Length: \(Int(length))")
                    Slider(value: $length, in: 8...64, step: 1)
                }
                Toggle("Uppercase letters", isOn: $upper)
                Toggle("Digits", isOn: $digits)
                Toggle("Symbols", isOn: $symbols)
                Toggle("Group in blocks of 6", isOn: $grouped)
            }
            .cardRow()
        }
        .themed()
        .navigationTitle("Generator")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } }
            ToolbarItem(placement: .confirmationAction) {
                if let onUse { Button("Use") { onUse(password) } }
            }
        }
        .onAppear(perform: regenerate)
        .onChange(of: length) { _ in regenerate() }
        .onChange(of: upper) { _ in regenerate() }
        .onChange(of: digits) { _ in regenerate() }
        .onChange(of: symbols) { _ in regenerate() }
        .onChange(of: grouped) { _ in regenerate() }
    }

    private func regenerate() {
        password = PasswordGenerator.generate(length: Int(length), upper: upper, digits: digits,
                                              symbols: symbols, grouped: grouped)
    }
}
