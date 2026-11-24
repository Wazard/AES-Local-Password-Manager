import Foundation
import Network
import CryptoKit
import UIKit

/// The messages exchanged with the PC (core/phone_transfer.py is the other side):
///
///     kind (4) | name length (1) | sender name | payload size (4, big-endian) | payload
///              | HMAC-SHA256(key = the code shown here, message = everything before)
///
/// SVX1: the PC replaces this iPhone's vault. SVY1/SVY2/SVY3: sync — the PC
/// asks for this vault, gets it, and sends back the merged one.
///
/// SVH1 on its own (no frame) is the PC's network probe, for when Bonjour
/// can't find this iPhone: it gets "HELLO <device name>" back.
enum TransferFrame {
    static let push = "SVX1", syncRequest = "SVY1", syncVault = "SVY2", syncMerged = "SVY3"
    static let hello = "SVH1"
    static let maxSize = 16 * 1024 * 1024

    enum Outcome: Equatable {
        case needMore
        /// The PC's probe (only where a first message is expected).
        case hello
        /// The reason sent back to the PC: badcode, toolarge, protocol.
        case rejected(String)
        case accepted(kind: String, sender: String, payload: Data)
    }

    static func parse(_ buffer: Data, code: String, accepting kinds: [String]) -> Outcome {
        let b = [UInt8](buffer)
        let opening = kinds.contains(push)
        if opening && b.count >= 4 && Array(b[0..<4]) == Array(hello.utf8) { return .hello }
        guard b.count >= 5 else {
            let starts = opening ? kinds + [hello] : kinds
            return starts.contains { Array(Array($0.utf8).prefix(b.count)) == b } ? .needMore : .rejected("protocol")
        }
        guard let kind = kinds.first(where: { Array($0.utf8) == Array(b[0..<4]) }) else { return .rejected("protocol") }
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
        return .accepted(kind: kind, sender: String(decoding: b[5..<sizeAt], as: UTF8.self),
                         payload: Data(b[(sizeAt + 4)..<bodyEnd]))
    }

    static func build(_ kind: String, payload: Data, sender: String, code: String) -> Data {
        let name = Array(sender.utf8.prefix(255))
        var body = Data(kind.utf8)
        body.append(UInt8(name.count))
        body.append(contentsOf: name)
        withUnsafeBytes(of: UInt32(payload.count).bigEndian) { body.append(contentsOf: $0) }
        body.append(payload)
        body.append(contentsOf: HMAC<SHA256>.authenticationCode(for: body, using: SymmetricKey(data: Data(code.utf8))))
        return body
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
        /// A sync finished; the vault file now holds the merged vault.
        case synced(String)
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
    /// False when iOS refused the Bonjour announcement, so the PC can't find
    /// this iPhone by itself and the address has to be typed there.
    @Published private(set) var announced = true

    private var listener: NWListener?
    private var wrongCodes = 0
    /// The vault a sync reads and replaces; nil when there is none yet.
    private var location: VaultLocation?

    func start(location: VaultLocation?) {
        self.location = location
        code = String(format: "%06d", Int.random(in: 0...999_999))
        wrongCodes = 0
        listen(announce: true)
    }

    private func listen(announce: Bool) {
        stop()
        announced = announce
        address = Self.wifiAddress()
        do {
            let parameters = NWParameters.tcp
            parameters.allowLocalEndpointReuse = true
            let listener = try NWListener(using: parameters, on: Self.port)
            if announce {
                listener.service = NWListener.Service(name: UIDevice.current.name, type: Self.serviceType)
            }
            listener.newConnectionHandler = { [weak self] connection in
                Task { @MainActor in self?.accept(connection) }
            }
            listener.stateUpdateHandler = { [weak self, weak listener] update in
                Task { @MainActor in
                    // Ignore a listener this one has already replaced.
                    guard let self, let listener, self.listener === listener else { return }
                    switch update {
                    case .failed(let error), .waiting(let error):
                        self.listenerFailed(error)
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

    /// kDNSServiceErr_NoAuth (-65555): iOS refused the Bonjour announcement.
    /// Either Local Network access is off, or the app runs inside another one
    /// (LiveContainer) whose Info.plist doesn't list our service type — which
    /// no setting can fix. So keep listening without announcing (same code);
    /// the PC connects by address. Only if that fails too is it the permission.
    private func listenerFailed(_ error: NWError) {
        if case .dns(let code) = error, code == -65555 {
            if announced {
                listen(announce: false)
            } else {
                stop()
                state = .needsLocalNetwork
            }
        } else {
            fail("Couldn't listen on the network: \(error.localizedDescription)")
        }
    }

    private func accept(_ connection: NWConnection) {
        guard state == .waiting else { connection.cancel(); return }
        connection.start(queue: .main)
        // A stalled sender doesn't get to hold the connection open.
        DispatchQueue.main.asyncAfter(deadline: .now() + 30) { connection.cancel() }
        read(connection, Data(), accepting: [TransferFrame.push, TransferFrame.syncRequest])
    }

    private func read(_ connection: NWConnection, _ buffer: Data, accepting kinds: [String]) {
        connection.receive(minimumIncompleteLength: 1, maximumLength: 256 * 1024) { [weak self] data, _, isComplete, error in
            Task { @MainActor in
                guard let self else { return connection.cancel() }
                var buffer = buffer
                if let data { buffer.append(data) }
                switch TransferFrame.parse(buffer, code: self.code, accepting: kinds) {
                case .needMore:
                    if isComplete || error != nil {
                        connection.cancel()
                    } else {
                        self.read(connection, buffer, accepting: kinds)
                    }
                case .hello:
                    self.reply(connection, "HELLO \(UIDevice.current.name)")
                case .rejected(let reason):
                    self.reply(connection, "ERR \(reason)")
                    if reason == "badcode" {
                        self.wrongCodes += 1
                        if self.wrongCodes >= Self.maxWrongCodes {
                            self.fail("Too many wrong codes. Start again to get a new one.")
                        }
                    }
                case .accepted(let kind, let sender, let payload):
                    self.handle(kind, sender: sender, payload: payload, on: connection)
                }
            }
        }
    }

    private func handle(_ kind: String, sender: String, payload: Data, on connection: NWConnection) {
        // Two PCs at once: the first one wins.
        guard state == .waiting else { return reply(connection, "ERR busy") }
        switch kind {
        case TransferFrame.push:
            guard VaultFormat.looksLikeVault(payload) else { return reply(connection, "ERR notvault") }
            reply(connection, "OK")
            stop()
            state = .received(ReceivedVault(sender: sender, data: payload))

        case TransferFrame.syncRequest:
            // The phone needn't be unlocked: only the encrypted file travels,
            // and the PC opens it with its own key.
            guard let location, let blob = try? VaultFiles.read(location) else {
                return reply(connection, "ERR novault")
            }
            let frame = TransferFrame.build(TransferFrame.syncVault, payload: blob,
                                            sender: UIDevice.current.name, code: code)
            connection.send(content: frame, completion: .contentProcessed { [weak self] error in
                Task { @MainActor in
                    guard let self, error == nil else { return connection.cancel() }
                    self.read(connection, Data(), accepting: [TransferFrame.syncMerged])
                }
            })

        case TransferFrame.syncMerged:
            guard VaultFormat.looksLikeVault(payload) else { return reply(connection, "ERR notvault") }
            guard let location else { return reply(connection, "ERR novault") }
            do {
                // The vault as it was before the sync stays in the backups.
                if let current = try? VaultFiles.read(location) { VaultFiles.makeBackup(current) }
                try VaultFiles.write(payload, to: location)
            } catch {
                return reply(connection, "ERR savefailed")
            }
            reply(connection, "OK")
            stop()
            state = .synced(sender)

        default:
            reply(connection, "ERR protocol")
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
