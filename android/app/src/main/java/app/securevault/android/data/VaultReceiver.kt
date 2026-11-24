package app.securevault.android.data

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Build
import android.provider.Settings
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import app.securevault.android.core.TransferFrame
import app.securevault.android.core.TransferFrame.Outcome
import app.securevault.android.core.VaultFormat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.OutputStream
import java.net.Inet4Address
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.ServerSocket
import java.net.Socket
import java.security.SecureRandom
import java.util.Locale

class ReceivedVault(val sender: String, val data: ByteArray)

/**
 * Listens on the local network while the Connect to PC screen is open.
 * Nothing listens otherwise, and it stops after one good transfer or a few
 * bad codes. The protocol is the one the iOS app speaks (core/phone_transfer.py
 * on the PC); see [TransferFrame].
 */
class VaultReceiver(private val context: Context, private val files: VaultFiles) {
    sealed interface State {
        data object Idle : State
        data object Waiting : State
        class Received(val vault: ReceivedVault) : State
        /** A sync finished; the vault file now holds the merged vault. */
        data class Synced(val sender: String) : State
        data class Failed(val message: String) : State
    }

    var state by mutableStateOf<State>(State.Idle)
        private set
    var code by mutableStateOf("")
        private set
    var address by mutableStateOf<String?>(null)
        private set
    /** False when Android refused the network announcement: the PC then only
     *  finds this phone by probing the network, or by its typed address. */
    var announced by mutableStateOf(true)
        private set

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var server: ServerSocket? = null
    private var registration: NsdManager.RegistrationListener? = null
    private var wrongCodes = 0
    /** The vault a sync reads and replaces; null when there is none yet. */
    private var location: VaultLocation? = null
    val deviceName: String by lazy { nameOf(context) }

    fun start(location: VaultLocation?) {
        stop()
        this.location = location
        code = String.format(Locale.ROOT, "%06d", SecureRandom().nextInt(1_000_000))
        wrongCodes = 0
        address = wifiAddress()
        val socket = try {
            ServerSocket().apply {
                reuseAddress = true
                bind(InetSocketAddress(PORT))
            }
        } catch (e: IOException) {
            state = State.Failed("Couldn't listen on the network: ${e.message}")
            return
        }
        server = socket
        state = State.Waiting
        announce()
        scope.launch(Dispatchers.IO) {
            while (true) {
                val client = try {
                    socket.accept()
                } catch (e: IOException) {
                    break   // closed by stop()
                }
                scope.launch { serve(client) }
            }
        }
    }

    fun stop() {
        registration?.let { listener ->
            try {
                context.getSystemService(NsdManager::class.java)?.unregisterService(listener)
            } catch (e: RuntimeException) {
                // Never registered.
            }
        }
        registration = null
        server?.let { closeQuietly(it) }
        server = null
        if (state == State.Waiting) state = State.Idle
    }

    fun discard() {
        state = State.Idle
    }

    /** The screen is gone for good. */
    fun close() {
        stop()
        scope.cancel()
    }

    private fun fail(message: String) {
        stop()
        state = State.Failed(message)
    }

    private fun announce() {
        val nsd = context.getSystemService(NsdManager::class.java)
        if (nsd == null) {
            announced = false
            return
        }
        val info = NsdServiceInfo().apply {
            serviceName = deviceName
            serviceType = SERVICE_TYPE
            port = PORT
        }
        val listener = object : NsdManager.RegistrationListener {
            override fun onServiceRegistered(serviceInfo: NsdServiceInfo) {}
            override fun onRegistrationFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                scope.launch { announced = false }
            }
            override fun onServiceUnregistered(serviceInfo: NsdServiceInfo) {}
            override fun onUnregistrationFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {}
        }
        try {
            nsd.registerService(info, NsdManager.PROTOCOL_DNS_SD, listener)
            registration = listener
            announced = true
        } catch (e: RuntimeException) {
            announced = false
        }
    }

    /** One connection. Runs on the main thread except for the blocking I/O. */
    private suspend fun serve(socket: Socket) {
        if (state != State.Waiting) {
            closeQuietly(socket)
            return
        }
        // A stalled sender doesn't get to hold the connection open.
        val watchdog = scope.launch {
            delay(30_000)
            closeQuietly(socket)
        }
        try {
            val input = socket.getInputStream()
            val output = socket.getOutputStream()
            var kinds = listOf(TransferFrame.PUSH, TransferFrame.SYNC_REQUEST)
            val buffer = ByteArrayOutputStream()
            val chunk = ByteArray(64 * 1024)
            var need = 1
            while (true) {
                if (buffer.size() < need) {
                    val n = withContext(Dispatchers.IO) { input.read(chunk) }
                    if (n < 0) return
                    buffer.write(chunk, 0, n)
                    if (buffer.size() < need) continue
                }
                when (val outcome = TransferFrame.parse(buffer.toByteArray(), code, kinds)) {
                    is Outcome.NeedMore -> need = maxOf(outcome.atLeast, buffer.size() + 1)
                    is Outcome.Hello -> {
                        reply(output, "HELLO $deviceName")
                        return
                    }
                    is Outcome.Rejected -> {
                        reply(output, "ERR ${outcome.reason}")
                        if (outcome.reason == "badcode") {
                            wrongCodes++
                            if (wrongCodes >= MAX_WRONG_CODES) fail("Too many wrong codes. Start again to get a new one.")
                        }
                        return
                    }
                    is Outcome.Accepted -> {
                        // Two PCs at once: the first one wins.
                        if (state != State.Waiting) {
                            reply(output, "ERR busy")
                            return
                        }
                        when (outcome.kind) {
                            TransferFrame.PUSH -> {
                                if (!VaultFormat.looksLikeVault(outcome.payload)) {
                                    reply(output, "ERR notvault")
                                    return
                                }
                                reply(output, "OK")
                                stop()
                                state = State.Received(ReceivedVault(outcome.sender, outcome.payload))
                                return
                            }
                            TransferFrame.SYNC_REQUEST -> {
                                // The phone needn't be unlocked: only the encrypted file
                                // travels, and the PC opens it with its own key.
                                val target = location
                                val blob = if (target == null) null else withContext(Dispatchers.IO) {
                                    try {
                                        files.read(target)
                                    } catch (e: Exception) {
                                        null
                                    }
                                }
                                if (blob == null) {
                                    reply(output, "ERR novault")
                                    return
                                }
                                val frame = TransferFrame.build(TransferFrame.SYNC_VAULT, blob, deviceName, code)
                                withContext(Dispatchers.IO) {
                                    output.write(frame)
                                    output.flush()
                                }
                                kinds = listOf(TransferFrame.SYNC_MERGED)
                                buffer.reset()
                                need = 1
                            }
                            TransferFrame.SYNC_MERGED -> {
                                val target = location
                                if (!VaultFormat.looksLikeVault(outcome.payload)) {
                                    reply(output, "ERR notvault")
                                    return
                                }
                                if (target == null) {
                                    reply(output, "ERR novault")
                                    return
                                }
                                val saved = withContext(Dispatchers.IO) {
                                    try {
                                        // The vault as it was before the sync stays in the backups.
                                        try {
                                            files.backups.make(files.read(target))
                                        } catch (e: Exception) {
                                            // Nothing to back up.
                                        }
                                        files.write(outcome.payload, target)
                                        true
                                    } catch (e: Exception) {
                                        false
                                    }
                                }
                                if (!saved) {
                                    reply(output, "ERR savefailed")
                                    return
                                }
                                reply(output, "OK")
                                stop()
                                state = State.Synced(outcome.sender)
                                return
                            }
                            else -> {
                                reply(output, "ERR protocol")
                                return
                            }
                        }
                    }
                }
            }
        } catch (e: IOException) {
            // The PC went away or the watchdog closed the connection.
        } finally {
            watchdog.cancel()
            closeQuietly(socket)
        }
    }

    private suspend fun reply(output: OutputStream, line: String) {
        withContext(Dispatchers.IO) {
            try {
                output.write((line + "\n").toByteArray(Charsets.UTF_8))
                output.flush()
            } catch (e: IOException) {
                // The PC hung up first.
            }
        }
    }

    private fun closeQuietly(closeable: java.io.Closeable) {
        try {
            closeable.close()
        } catch (e: IOException) {
            // Already closed.
        }
    }

    companion object {
        const val PORT = 53917
        const val SERVICE_TYPE = "_securevault._tcp"
        private const val MAX_WRONG_CODES = 5

        fun nameOf(context: Context): String =
            Settings.Global.getString(context.contentResolver, Settings.Global.DEVICE_NAME)?.takeIf { it.isNotBlank() }
                ?: "${Build.MANUFACTURER.replaceFirstChar { it.titlecase(Locale.ROOT) }} ${Build.MODEL}"

        /** The Wi-Fi IPv4 address, for typing into the PC if it can't find the phone. */
        fun wifiAddress(): String? = try {
            val candidates = NetworkInterface.getNetworkInterfaces()?.toList().orEmpty()
                .filter { it.isUp && !it.isLoopback }
                .flatMap { iface ->
                    iface.inetAddresses.toList().filterIsInstance<Inet4Address>()
                        .filter { !it.isLinkLocalAddress }
                        .mapNotNull { addr -> addr.hostAddress?.let { iface.name to it } }
                }
            (candidates.firstOrNull { it.first.startsWith("wlan") }
                ?: candidates.firstOrNull { !it.first.startsWith("rmnet") && !it.first.startsWith("tun") })?.second
        } catch (e: Exception) {
            null
        }
    }
}
