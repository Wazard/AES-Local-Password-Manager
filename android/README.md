# Secure Vault for Android

A native Kotlin / Jetpack Compose app that opens the **same `.pwmanager`
file** as the Windows and iOS apps: same Argon2id + AES-256-GCM format, same
gzip+JSON payload, same entry order, unknown fields kept as they are. Legacy
(PBKDF2) vaults open too and are upgraded on the next save. It is a port of
the iOS app (`ios/`) and follows the same rules; the one difference is
**fingerprint unlock** in place of Face ID.

Android 8.0 or later.

## Getting the .apk

The `Android app` GitHub Actions workflow (`.github/workflows/android.yml`)
builds it on every change to `android/`, `core/` or the palette, or on demand
from **Actions › Android app › Run workflow**. It:

1. runs the unit tests on the JVM. They open the vaults the desktop's own
   Python code wrote (`ios/SecureVaultTests/Fixtures`, shared with the iOS
   tests) and run the shared search cases,
2. checks that the desktop code can open a vault written by the Android code
   and merge its sync marks (`ios/tools/check_roundtrip.py`, `check_sync.py`),
3. builds `SecureVault-<version>.apk` and attaches it to the run as an
   artifact (it downloads as a .zip with the .apk inside).

Copy the .apk to the phone and open it. Android asks once to allow installing
apps from that source (the Files app or the browser).

### Signing: set this up once

Android only installs an update over an existing app if both are signed with
the same key. Without a key of your own, CI signs every build with a
throwaway debug key, so each new build has to be installed fresh, and
**uninstalling deletes a vault stored in the app**. (A vault opened from
OneDrive is not affected, and the backups go too.)

To sign with your own key, make one once with `keytool`. It comes with any
JDK, or with Android Studio as `jbr\bin\keytool`:

```
keytool -genkeypair -v -keystore securevault.jks -alias securevault -keyalg RSA -keysize 4096 -validity 10000
```

Then add four repository secrets under **Settings › Secrets and variables ›
Actions**:

| Secret | Value |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | the file, base64-encoded (PowerShell: `[Convert]::ToBase64String([IO.File]::ReadAllBytes("securevault.jks"))`) |
| `ANDROID_KEYSTORE_PASSWORD` | the keystore password |
| `ANDROID_KEY_ALIAS` | `securevault` |
| `ANDROID_KEY_PASSWORD` | the key password (the same as the keystore's, unless you chose another) |

Keep `securevault.jks` safe and out of the repository (`.gitignore` already
excludes `*.jks`). If you lose it, the next build can't update the installed
app.

## Using it with the PC vault

On first launch choose **Open an existing vault** and pick `vault.pwmanager`
in the system file picker, for example in OneDrive (the OneDrive app must be
installed so it shows up in the picker). The file is edited in place, so
changes show up on the PC too. Before every save the app re-reads the file.
If the PC saved in the meantime, the PC's version is loaded first and your
change is applied on top of it, so neither side's edits are overwritten.

### Or sync with the PC over Wi-Fi

Exactly as with the iPhone, using the same protocol:

1. On the phone tap **Get your vault from your PC over Wi-Fi** (first screen),
   **Connect to PC** (lock screen), or **Settings › Sync with PC over Wi-Fi**.
   It shows a 6-digit code and the phone's address.
2. On the PC click the **phone icon** in the top bar. The phone appears in
   the list; if it doesn't, type the address the phone shows.
3. Type the code and click **Sync** (or **Replace phone vault** the first
   time), then on the phone tap **Use this vault** and unlock with your
   master password.

The phone announces itself on the network (Android's network service
discovery), and the PC also probes the local network for the app's port, so
it is found even where announcements don't get through. Only the encrypted
vault file travels; the code proves it came from your PC, and the phone stops
listening after one transfer or five wrong codes. A VPN on the phone or the
PC has to allow local network traffic.

## Fingerprint unlock

**Settings › Unlock with fingerprint** stores the derived vault key (never the
master password), encrypted with an Android Keystore key that needs a strong
biometric (a fingerprint, or a face on phones with a class 3 face sensor) for
every use. That key stays in the phone's secure hardware, and Android deletes
it when a fingerprint is added or removed. The app then asks for the master
password and you turn fingerprint unlock on again. The same happens after the
master password changes, here or on the PC.

## What's in it

Unlock (master password or fingerprint), search, the four sorts, favourites,
add / edit / rename / delete, reveal and copy (the copy is marked sensitive
and the clipboard clears itself), password generator, master-password change,
backups and restore, and sync with the PC. The app locks when it leaves the
screen, right away or after a delay you choose. Screenshots are blocked and
the recent-apps preview is blank.

Backups are kept inside the app's private storage (same names and retention as
the desktop). There is no Android cloud backup of the app's data: keep the PC
in sync, or open the vault from OneDrive, so a lost phone loses nothing.

Not ported: the browser extension bridge, autofill into other apps,
translations, and the Windows-only parts.

## Building locally

Open `android/` in Android Studio, which brings its own JDK and SDK, and run
the `app` configuration; or, with JDK 17, the Android SDK and Gradle 8.11:

```
cd android
gradle :app:testDebugUnitTest :app:assembleDebug
```

There is no Gradle wrapper in the repository. Android Studio offers to add
one, and CI uses a pinned Gradle version instead. Argon2id comes from Bouncy
Castle; `UI/palette.json` is copied into the app at build time, so the colours
follow the desktop's.
