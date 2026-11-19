import Foundation
import Network
import CryptoKit
import UIKit

/// The message the PC sends (see core/phone_transfer.py for the other side):
///
///     "SVX1" | name length (1) | PC name | vault size (4, big-endian) | vault
///            | HMAC-SHA256(key = the code shown here, message = everything before)
enum TransferFrame {
    static let magic = Array("SVX1".utf8)
    static let maxSize = 16 * 1024 * 1024

    enum Outcome: Equatable {
        case needMore
        /// The reason sent back to the PC: badcode, toolarge, notvault, protocol.
        case rejected(String)
        case accepted(sender: String, vault: Data)
    }

    static func parse(_ buffer: Data, code: String) -> Outcome {
        let b = [UInt8](buffer)
        guard b.count >= 5 else { return Array(b.prefix(4)) == Array(magic.prefix(b.count)) ? .needMore : .rejected("protocol") }
        guard Array(b[0..<4]) == magic else { return .rejected("protocol") }
        let nameLength = Int(b[4])
        let sizeAt = 5 + nameLength
        guard b.count >= sizeAt + 4 else { return .needMore }
        let size = Int(b[sizeAt]) << 24 | Int(b[sizeAt + 1]) << 16 | Int(b[sizeAt + 2]) << 8 | Int(b[sizeAt + 3])
        guard size <= maxSize else { return .rejected("toolarge") }
        let bodyEnd = sizeAt + 4 + size
        guard b.count >= bodyEnd + 32 else { return .needMore }
        guard b.count == bodyEnd + 32 else { return .rejected("protocol") }

        let valid = HMAC<SHA256>.isValidAuthenticationCode(
            Data(b[bodyEnd...]), authenticating: Data(b[0..<bodyEnd]),
            using: SymmetricKey(data: Data(code.utf8)))
        guard valid else { return .rejected("badcode") }
        let vault = Data(b[(sizeAt + 4)..<bodyEnd])
        guard VaultFormat.looksLikeVault(vault) else { return .rejected("notvault") }
        return .accepted(sender: String(decoding: b[5..<sizeAt], as: UTF8.self), vault: vault)
    }
}

struct ReceivedVault: Equatable {
    let sender: String
    let data: Data
}

/// Listens on the local network while the Receive screen is open. Nothing
/// listens otherwise, and it stops after one good transfer or a few bad codes.
@MainActor
final class VaultReceiver: ObservableObject {
    enum State: Equatable {
        case idle
        case waiting
        case received(ReceivedVault)
        case failed(String)
        /// iOS hasn't allowed Local Network access (yet): on the very first
        /// try it fails while its own permission prompt is still on screen.
        case needsLocalNetwork
    }

    static let port: NWEndpoint.Port = 53917
    static let serviceType = "_securevault._tcp"
    private static let maxWrongCodes = 5

    @Published private(set) var state = State.idle
    @Published private(set) var code = ""
    @Published private(set) var address: String?

    private var listener: NWListener?
    private var wrongCodes = 0

    func start() {
        stop()
        code = String(format: "%06d", Int.random(in: 0...999_999))
        wrongCodes = 0
        address = Self.wifiAddress()
        do {
            let parameters = NWParameters.tcp
            parameters.allowLocalEndpointReuse = true
            let listener = try NWListener(using: parameters, on: Self.port)
            listener.service = NWListener.Service(name: UIDevice.current.name, type: Self.serviceType)
            listener.newConnectionHandler = { [weak self] connection in
                Task { @MainActor in self?.accept(connection) }
            }
            listener.stateUpdateHandler = { [weak self] update in
                Task { @MainActor in
                    switch update {
                    case .failed(let error), .waiting(let error):
                        self?.listenerFailed(error)
                    default:
                        break
                    }
                }
            }
            listener.start(queue: .main)
            self.listener = listener
            state = .waiting
            UIApplication.shared.isIdleTimerDisabled = true
        } catch {
            fail("Couldn't listen on the network: \(error.localizedDescription)")
        }
    }

    func stop() {
        listener?.cancel()
        listener = nil
        UIApplication.shared.isIdleTimerDisabled = false
        if state == .waiting { state = .idle }
    }

    func discard() {
        state = .idle
    }

    private func fail(_ message: String) {
        stop()
        state = .failed(message)
    }

    /// kDNSServiceErr_NoAuth (-65555): Bonjour refused because Local Network
    /// access is off — the one failure the user can fix, so it gets its own state.
    private func listenerFailed(_ error: NWError) {
        if case .dns(let code) = error, code == -65555 {
            stop()
            state = .needsLocalNetwork
        } else {
            fail("Couldn't listen on the network: \(error.localizedDescription)")
        }
    }

    private func accept(_ connection: NWConnection) {
        guard state == .waiting else { connection.cancel(); return }
        connection.start(queue: .main)
        // A stalled sender doesn't get to hold the connection open.
        DispatchQueue.main.asyncAfter(deadline: .now() + 30) { connection.cancel() }
        read(connection, Data())
    }

    private func read(_ connection: NWConnection, _ buffer: Data) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 256 * 1024) { [weak self] data, _, isComplete, error in
            Task { @MainActor in
                guard let self else { return connection.cancel() }
                var buffer = buffer
                if let data { buffer.append(data) }
                switch TransferFrame.parse(buffer, code: self.code) {
                case .needMore:
                    if isComplete || error != nil { connection.cancel() } else { self.read(connection, buffer) }
                case .rejected(let reason):
                    self.reply(connection, "ERR \(reason)")
                    if reason == "badcode" {
                        self.wrongCodes += 1
                        if self.wrongCodes >= Self.maxWrongCodes {
                            self.fail("Too many wrong codes. Start again to get a new one.")
                        }
                    }
                case .accepted(let sender, let vault):
                    // Two PCs sending at once: the first one wins.
                    guard self.state == .waiting else { return self.reply(connection, "ERR busy") }
                    self.reply(connection, "OK")
                    self.stop()
                    self.state = .received(ReceivedVault(sender: sender, data: vault))
                }
            }
        }
    }

    private func reply(_ connection: NWConnection, _ line: String) {
        connection.send(content: Data((line + "\n").utf8), completion: .contentProcessed { _ in
            connection.cancel()
        })
    }

    /// The Wi-Fi IPv4 address, for typing into the PC if discovery can't find the phone.
    static func wifiAddress() -> String? {
        var head: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&head) == 0, let first = head else { return nil }
        defer { freeifaddrs(head) }
        var found: String?
        for ptr in sequence(first: first, next: { $0.pointee.ifa_next }) {
            let ifa = ptr.pointee
            guard let addr = ifa.ifa_addr, addr.pointee.sa_family == UInt8(AF_INET) else { continue }
            let name = String(cString: ifa.ifa_name)
            guard name.hasPrefix("en") else { continue }   // en0 is Wi-Fi on iPhone
            var host = [CChar](repeating: 0, count: Int(NI_MAXHOST))
            if getnameinfo(addr, socklen_t(addr.pointee.sa_len), &host, socklen_t(host.count),
                           nil, 0, NI_NUMERICHOST) == 0 {
                let ip = String(cString: host)
                if name == "en0" { return ip }
                found = found ?? ip
            }
        }
        return found
    }
}
