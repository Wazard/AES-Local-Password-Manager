package app.securevault.android

import android.graphics.Color
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.fragment.app.FragmentActivity
import app.securevault.android.data.authenticate
import app.securevault.android.ui.Palette
import app.securevault.android.ui.Root
import app.securevault.android.ui.SecureVaultTheme

/** A FragmentActivity because the system fingerprint prompt needs one. */
class MainActivity : FragmentActivity() {
    private val store: VaultStore by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // No screenshots, and a blank card in the recent-apps switcher.
        window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(Color.TRANSPARENT),
        )
        Palette.load(this)
        val prompt: Authenticate = { cipher ->
            authenticate(cipher, "Unlock Secure Vault", "Touch the fingerprint sensor")
        }
        setContent {
            SecureVaultTheme { Root(store, prompt) }
        }
    }
}
