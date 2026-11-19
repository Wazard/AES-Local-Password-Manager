"""Secure Vault — main application window.

The screens live in dedicated mixins (UI/screen_*.py); this file wires them
together and owns shared state and the window/tray lifecycle.
"""
import os
import time
import json
import threading
import customtkinter as ctk

from core import encryption
from core import storage_handler
from core import storage_compression
from core import data_handler
from core import app_config
from core import password_generator
from core import password_strength
from core import protocol_handler
from core import tamper
from core import backup
from core import vault_location
from core.autofill_server import AutofillServer
from core.single_instance import ControlServer
from core.session_crypto import SessionCrypto
from localization.language_manager import LanguageManager

from UI import components as ui
from UI import theme as T
from UI.theme import apply_theme
from UI.tray import TrayManager, TRAY_AVAILABLE
from UI.screen_auth import AuthMixin
from UI.screen_dashboard import DashboardMixin
from UI.screen_entry import EntryMixin
from UI.screen_generator import GeneratorMixin
from UI.screen_extension import ExtensionMixin
from UI.screen_backup import BackupMixin
from UI.screen_changepw import ChangeMasterMixin
from UI.screen_phone import PhoneMixin

apply_theme()

# Kept screens that show what is in the vault, dropped whenever it locks.
VAULT_SCREENS = ("dashboard", "details", "form")


class _KeptScreen:
    """A screen built once and kept; see PasswordManagerGUI.open_screen."""
    __slots__ = ("frame", "under", "refresh", "leave")

    def __init__(self, frame, under):
        self.frame = frame
        self.under = under
        self.refresh = None
        self.leave = None


AUTO_LOCK_MS = 5 * 60 * 1000      # re-lock after 5 minutes of inactivity
IDLE_WARNING_MS = 30 * 1000       # heads-up shown before the auto-lock fires
CLIPBOARD_CLEAR_MS = 25 * 1000    # wipe copied secrets from the clipboard


class PasswordManagerGUI(ctk.CTk, AuthMixin, DashboardMixin, EntryMixin,
                         GeneratorMixin, ExtensionMixin, BackupMixin,
                         ChangeMasterMixin, PhoneMixin):
    def __init__(self):
        super().__init__()

        # Localization / navigation state
        self.lang_manager = LanguageManager()
        self.current_lang = "en"
        self.current_view = "auth"
        self.active_service = None  # For detail/modify tracking

        # Dashboard search / sort / view state
        self.search_query = ""
        self.sort_mode = "name_asc"
        self.view_mode = "list"
        self.logged_in = False

        # Generator animation state
        self._gen_token = 0
        self._gen_after = None

        self.title("Secure Vault")
        self.geometry("%dx%d" % (T.WINDOW_W, T.WINDOW_H))
        self.minsize(T.WINDOW_MIN_W, T.WINDOW_MIN_H)
        self.configure(fg_color=T.BG)

        # Exposed so the copy buttons can show the clipboard countdown.
        self.clipboard_clear_ms = CLIPBOARD_CLEAR_MS
        # Why the vault locked, so the login screen can explain itself.
        self.lock_reason = None

        # System tray
        self._icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        self.minimize_to_tray = ctk.BooleanVar(value=False)
        self.tray = TrayManager(self, self._icon_path, self.t)
        try:
            self.iconbitmap(self._icon_path)
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Persisted config (extension pairing + last language)
        self.ext_config = app_config.load()
        self.current_lang = self.ext_config.get("language", "en")
        self.ext_port = self.ext_config.get("port", app_config.DEFAULT_PORT)
        self.ext_enabled = ctk.BooleanVar(value=self.ext_config.get("enabled", False))
        self.autofill_server = None
        if self.ext_enabled.get():
            self._start_autofill()
            self._ensure_protocol(True)  # browser-launch goes with the server

        # Anti-tamper protection (opt-in; off by default)
        self.tamper_enabled = ctk.BooleanVar(value=self.ext_config.get("tamper_protection", False))

        # Single-instance control channel + securevault:// launch handler
        self._control = None

        # Vault session — only the derived key is kept (never the master
        # password), and passwords are held encrypted with a per-session key.
        self.vault_key = None
        self.vault_salt = None
        self.vault_params = None
        self.vault_data = {}
        self.session = SessionCrypto()
        # Bumped on every edit; the search cache and the dashboard use it to
        # tell "same accounts, redraw pointless" from "this is stale".
        self.vault_revision = 0
        self.search_cache = data_handler.SearchCache()
        # True only while the user is deliberately setting up a new vault, so a
        # missing (moved) vault can never be replaced by an empty one.
        self.creating_vault = False

        # Auto-lock on inactivity + tamper tripwire
        self._idle_after = None
        self._idle_warn_after = None
        self._idle_warning = None
        self._tamper_after = None
        self.bind_all("<Key>", self._on_activity, add="+")
        self.bind_all("<ButtonPress>", self._on_activity, add="+")

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        # Kept for the whole session: the top bar, and the dashboard once built.
        self.app_bar = ui.AppBar(self)
        self.app_bar.pack(fill="x", side="top")
        # Every screen is built once and kept (see open_screen); they are
        # stacked in here.
        self.host = ctk.CTkFrame(self.container, fg_color="transparent")
        self.host.pack(fill="both", expand=True)
        self.screen = None
        self._kept = {}        # screen name -> _KeptScreen
        self._showing = None   # name of the screen on top

        self.show_auth_screen()
        self.after(600, self._maybe_show_tamper_notice)

    def _maybe_show_tamper_notice(self):
        """One-time heads-up that anti-tamper protection exists and is opt-in."""
        if self.ext_config.get("tamper_notice_seen"):
            return
        self.ext_config["tamper_notice_seen"] = True
        try:
            app_config.save(self.ext_config)
        except Exception:
            pass
        ui.alert(self, self.t("security.tamper_notice_title"),
                 self.t("security.tamper_notice_msg"))

    # --- Auto-lock ---
    def _on_activity(self, _event=None):
        if self.logged_in:
            self._reset_idle_timer()

    def _reset_idle_timer(self):
        for attr in ("_idle_after", "_idle_warn_after"):
            handle = getattr(self, attr, None)
            if handle is not None:
                try:
                    self.after_cancel(handle)
                except Exception:
                    pass
                setattr(self, attr, None)
        if self._idle_warning is not None:
            try:
                self._idle_warning.destroy()
            except Exception:
                pass
            self._idle_warning = None
        # "Remember me" (keep running in tray) opts out of the idle auto-lock;
        # the tamper tripwire below is the safety net for a long-lived session.
        if self.minimize_to_tray.get():
            return
        self._idle_warn_after = self.after(
            max(AUTO_LOCK_MS - IDLE_WARNING_MS, 0), self._warn_idle)
        self._idle_after = self.after(AUTO_LOCK_MS, self._auto_lock)

    def _warn_idle(self):
        """Countdown banner before the vault locks itself."""
        self._idle_warn_after = None
        if not self.logged_in or self._idle_warning is not None:
            return
        self._idle_warning = ui.idle_banner(
            self, int(IDLE_WARNING_MS / 1000), self._on_activity)

    def _auto_lock(self):
        if self.logged_in:
            self.logout(reason="idle")

    # --- Tamper tripwire: lock instantly if a debugger attaches (opt-in) ---
    def start_security_timers(self):
        self._reset_idle_timer()
        if self.tamper_enabled.get() and self._tamper_after is None:
            self._tamper_check()

    def toggle_tamper(self):
        self.ext_config["tamper_protection"] = self.tamper_enabled.get()
        try:
            app_config.save(self.ext_config)
        except Exception:
            pass
        if self.tamper_enabled.get():
            if self.logged_in and self._tamper_after is None:
                self._tamper_check()
        elif self._tamper_after is not None:
            try:
                self.after_cancel(self._tamper_after)
            except Exception:
                pass
            self._tamper_after = None
        if self.current_view == "extension":
            self.show_extension_screen()

    def _tamper_check(self):
        if not self.logged_in:
            self._tamper_after = None
            return
        if tamper.debugger_attached():
            self._tamper_after = None
            self.logout(reason="tamper")
            ui.alert(self, self.t("security.tamper_title"),
                     self.t("security.tamper_msg"), kind="warning")
            return
        self._tamper_after = self.after(1500, self._tamper_check)

    # --- Browser-extension autofill ---
    def get_extension_token(self):
        return app_config.get_or_create_token(self.ext_config)

    def _autofill_unlocked(self):
        return self.logged_in

    def _autofill_lookup(self, domain):
        names = data_handler.match_domain(self.vault_data, domain)
        return [{"name": n,
                 "user": self.vault_data[n].get("user", ""),
                 "pass": self.get_password(n)} for n in names]

    def _autofill_add(self, data):
        """Called from the server thread; marshals the add to the Tk thread."""
        result = {}
        done = threading.Event()

        def work():
            try:
                result["ok"] = self._add_credential(data)
            finally:
                done.set()

        self.after(0, work)
        done.wait(timeout=5)
        return result.get("ok", False)

    def _add_credential(self, data):
        if not self.logged_in:
            return False
        pwd = data.get("pass", "")
        base = (data.get("name") or data.get("domain") or "").strip()
        if not base or not pwd:
            return False
        name = base
        i = 2
        while name in self.vault_data:
            name = f"{base} ({i})"
            i += 1
        self.vault_data[name] = {
            "user": data.get("user", ""),
            "pass": self.session.encrypt(pwd),
            "url": data.get("domain", ""),
            "created": time.time(),
            "favourite": False,
        }
        ok = self._persist_vault()
        if ok and self.current_view == "dashboard":
            self.show_dashboard()
        return ok

    def _autofill_generate(self):
        return password_generator.generate_secure_password()

    # --- Master password ---
    def _verify_master(self, password):
        if self.vault_key is None:
            return False
        try:
            import hmac
            candidate = encryption.derive_key_with(password, self.vault_salt, self.vault_params)
            return hmac.compare_digest(candidate, self.vault_key)
        except Exception:
            return False

    def change_master(self, current, new):
        """Re-keys the vault to a new master password. Returns a status string."""
        if not self._verify_master(current):
            return "wrong_current"
        if not password_strength.evaluate(new)["ok"]:
            return "weak"
        self.vault_key, self.vault_salt, self.vault_params = encryption.derive_new(new)
        return "ok" if self._persist_vault() else "save_failed"

    # --- Single-instance / launch handling ---
    def start_control_server(self):
        self._control = ControlServer(lambda: self.after(0, self._restore_window))
        try:
            self._control.start()
        except Exception:
            self._control = None  # focus-on-relaunch unavailable; app still runs

    def _restore_window(self):
        """Bring the window to the front in response to a second launch.

        Covers both states the window may be in: withdrawn to the tray (the
        common case) and merely minimised/behind other windows. The brief
        topmost toggle forces Windows to actually raise it past focus-stealing
        prevention rather than just flashing the taskbar button."""
        try:
            self.deiconify()
            self.lift()
            self.attributes("-topmost", True)
            self.attributes("-topmost", False)
            self.focus_force()
        except Exception:
            pass

    def _ensure_protocol(self, enabled):
        """Browser-launch (securevault://) is tied to the autofill server: the
        extension can't open the app without it, so they go together."""
        try:
            protocol_handler.register() if enabled else protocol_handler.unregister()
        except Exception:
            pass

    def _start_autofill(self):
        token = self.get_extension_token()
        self.autofill_server = AutofillServer(
            "127.0.0.1", self.ext_port, token,
            self._autofill_unlocked, self._autofill_lookup,
            self._autofill_add, self._autofill_generate)
        try:
            self.autofill_server.start()
        except Exception:
            # Port already in use (e.g. another instance) — fail quietly.
            self.autofill_server = None

    def _stop_autofill(self):
        if self.autofill_server is not None:
            self.autofill_server.stop()
            self.autofill_server = None

    def toggle_extension(self):
        enabled = self.ext_enabled.get()
        self.ext_config["enabled"] = enabled
        self.ext_config["port"] = self.ext_port
        app_config.save(self.ext_config)
        if enabled:
            self._start_autofill()
        else:
            self._stop_autofill()
        self._ensure_protocol(enabled)  # browser-launch follows the server
        if self.current_view == "extension":
            self.show_extension_screen()

    def regenerate_token(self):
        self.ext_config["token"] = None
        new_token = app_config.get_or_create_token(self.ext_config)
        if self.autofill_server is not None:
            self.autofill_server.token = new_token
        if self.current_view == "extension":
            self.show_extension_screen()

    # --- Window lifecycle ---
    def _on_close(self):
        """Minimise to the Windows tray when the toggle is on; otherwise quit."""
        if self.minimize_to_tray.get() and TRAY_AVAILABLE:
            self.tray.hide()
        else:
            self.tray.stop()
            self.destroy()

    def destroy(self):
        # Single cleanup point for both the window-close and tray-quit paths.
        if self._control is not None:
            try:
                self._control.stop()
            except Exception:
                pass
            self._control = None
        self._stop_autofill()
        super().destroy()

    # --- Pointing the app at a vault file ---
    def locate_vault(self):
        """Adopt a vault file wherever the user keeps it. The file stays put —
        only its location is recorded — so moving the vault is a matter of
        pointing the app at it again, not of starting over."""
        from tkinter import filedialog
        src = filedialog.askopenfilename(
            title=self.t("vault.locate_title"),
            filetypes=[("Secure Vault", "*.pwmanager"), ("All files", "*.*")])
        if not src:
            return
        if not storage_handler.looks_like_vault(src):
            ui.alert(self, self.t("vault.locate_title"), self.t("vault.not_a_vault"))
            return
        self.use_vault_at(src)

    def use_vault_at(self, path):
        vault_location.remember(path)
        self.creating_vault = False
        self.show_auth_screen()  # vault now present → normal login

    def start_new_vault(self):
        """Deliberately start an empty vault. When a vault was in use before,
        say plainly that this app will stop using it."""
        if storage_handler.vault_state() == storage_handler.MOVED:
            # The in-app modal is not blocking, so the rest continues in the
            # callback rather than on a returned yes/no.
            ui.confirm(self, self.t("vault.create_title"),
                       self.t("vault.create_confirm"), self._begin_new_vault,
                       danger=False)
            return
        self._begin_new_vault()

    def _begin_new_vault(self):
        if storage_handler.vault_state() == storage_handler.MOVED:
            vault_location.remember(vault_location.default_path())
        self.creating_vault = True
        self.show_auth_screen()

    def cancel_new_vault(self):
        self.creating_vault = False
        self.show_auth_screen()

    def logout(self, reason=None):
        """Clear the decrypted session (key + vault) and return to login."""
        self.lock_reason = reason
        for attr in ("_idle_after", "_idle_warn_after", "_tamper_after"):
            handle = getattr(self, attr, None)
            if handle is not None:
                try:
                    self.after_cancel(handle)
                except Exception:
                    pass
                setattr(self, attr, None)
        self.vault_key = None
        self.vault_salt = None
        self.vault_params = None
        self.vault_data = {}
        self.session.rotate()
        self.search_query = ""
        self.sort_mode = "name_asc"
        self.view_mode = "list"
        self.logged_in = False
        self._idle_warning = None
        self.creating_vault = False
        # These show account names and details: never keep them past a lock.
        self.drop_screens(VAULT_SCREENS)
        self.show_auth_screen()

    # --- Shared helpers ---
    def t(self, key, **kwargs):
        """Translation helper."""
        return self.lang_manager.get_text(key, self.current_lang, **kwargs)

    def change_language(self, new_lang):
        """Refresh the current screen with the new language and remember it."""
        self.current_lang = new_lang
        self.ext_config["language"] = new_lang
        try:
            app_config.save(self.ext_config)
        except Exception:
            pass
        self.drop_screens()  # every kept screen is labelled in the old language
        view_map = {
            "auth": self.show_auth_screen,
            "dashboard": self.show_dashboard,
            "add": lambda: self.show_add_screen(),
            "modify": lambda: self.show_add_screen(self.active_service),
            "details": lambda: self.show_details(self.active_service),
            "generator": self.show_gen_pass_screen,
            "extension": self.show_extension_screen,
            "backup": self.show_backup_screen,
            "changepw": self.show_change_master_screen,
            "phone": self.show_phone_screen,
        }
        view_map[self.current_view]()

    def open_screen(self, name, build, refresh=None, leave=None, under=False):
        """Show the screen called `name`, building it only the first time.

        Building CustomTkinter widgets is what made every click slow, so each
        screen is laid out once and kept for the session. `build()` fills
        `self.screen` on the first visit; `refresh()` runs on every visit to
        bring the kept widgets up to date; `leave()` runs when the user moves
        on, and is where a screen wipes any secret it was showing.

        A screen left with `under=True` stays mapped beneath the others
        instead of being hidden. That is for the dashboard: un-hiding a window
        makes Windows re-show every widget on it, about 10 ms per account
        card, while uncovering one costs next to nothing.
        """
        kept = self._kept.get(name)
        if kept is not None and not kept.frame.winfo_exists():
            kept = None
        if kept is not None and self._showing == name:
            # Already on top (a toggle refreshing its own screen).
            kept.refresh, kept.leave = refresh, leave
            if refresh is not None:
                refresh()
            return kept.frame

        self._hide_screens()
        if kept is None:
            self.screen = ctk.CTkFrame(self.host, fg_color="transparent")
            build()
            kept = _KeptScreen(self.screen, under)
            self._kept[name] = kept
        kept.refresh, kept.leave = refresh, leave
        self.screen = kept.frame
        kept.frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        kept.frame.lift()
        self._showing = name
        if refresh is not None:
            refresh()
        return kept.frame

    def _hide_screens(self):
        """Take down whatever is showing. Kept screens are hidden (or, for
        `under` ones, just covered); anything else on the container — a modal,
        the idle banner — is destroyed, as it always was."""
        for widget in self.container.winfo_children():
            if widget is not self.app_bar and widget is not self.host:
                widget.destroy()
        kept = self._kept.get(self._showing)
        self._showing = None
        if kept is not None and kept.frame.winfo_exists():
            # Keep the keyboard out of a screen that is no longer on top.
            try:
                focused = self.focus_get()
            except Exception:  # Tk can't name some transient focus owners
                focused = None
            if focused is not None and str(focused).startswith(str(kept.frame) + "."):
                self.focus_set()
            if kept.leave is not None:
                kept.leave()
            if not kept.under:
                kept.frame.place_forget()

    def drop_screens(self, names=None):
        """Throw kept screens away (all of them, or those in `names`); each is
        built afresh on its next visit."""
        for name in list(self._kept) if names is None else names:
            kept = self._kept.pop(name, None)
            if kept is None:
                continue
            if self._showing == name:
                self._showing = None
            try:
                kept.frame.destroy()
            except Exception:
                pass

    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        # Auto-clear so secrets don't linger in the clipboard.
        self.after(CLIPBOARD_CLEAR_MS, lambda: self._clear_clipboard(text))

    def _clear_clipboard(self, text):
        try:
            if self.clipboard_get() == text:  # only if unchanged since
                self.clipboard_clear()
                self.clipboard_append("")
        except Exception:
            pass

    # --- Vault crypto (passwords stay session-encrypted in memory) ---
    def ingest_vault(self, plain_dict):
        """Loads a freshly decrypted vault, re-encrypting each password with a
        new per-session key so plaintext doesn't linger in memory."""
        self.session.rotate()
        self.vault_data = {}
        for service, entry in plain_dict.items():
            entry = dict(entry)
            entry["pass"] = self.session.encrypt(entry.get("pass", ""))
            self.vault_data[service] = entry
        self.vault_changed()

    def vault_changed(self):
        """Announce that `vault_data` was edited. The revision is what the
        search cache and the dashboard watch to know their results went stale."""
        self.vault_revision += 1

    def get_password(self, service):
        """Decrypts a single password on demand (only when actually needed)."""
        entry = self.vault_data.get(service, {})
        try:
            return self.session.decrypt(entry.get("pass", ""))
        except Exception:
            return entry.get("pass", "")

    def _persist_vault(self):
        """Writes the vault to disk. Builds a transient plaintext copy, encrypts
        it with the master password, and discards the plaintext. No UI."""
        self.vault_changed()  # every write follows an edit — here so no caller forgets
        plain = None
        try:
            plain = {}
            for service, entry in self.vault_data.items():
                pe = dict(entry)
                pe["pass"] = self.get_password(service)
                plain[service] = pe
            if self.vault_key is None:
                return False
            compressed = storage_compression.compress_data(json.dumps(plain))
            encrypted = encryption.encrypt_with_key(
                compressed, self.vault_key, self.vault_salt, self.vault_params)
            storage_handler.write_vault(encrypted)
        except Exception:
            return False
        finally:
            plain = None
        # A dated copy of every saved state. Never let a backup problem (full
        # disk, OneDrive offline) turn a successful save into a failed one.
        try:
            backup.make_backup(storage_handler.vault_path())
        except Exception:
            pass
        return True

    def save_vault(self):
        """Persist the vault after an edit."""
        ok = self._persist_vault()
        if not ok:
            ui.alert(self, self.t("modal.save_failed_title"),
                     self.t("modal.save_failed_msg"), kind="negative")
        return ok

    def restore_backup(self, backup_path):
        """Swap a backup in as the live vault, then send the user back to the
        login screen: the restored copy may well have a different master
        password, and everything decrypted in this session is now stale."""
        ok, msg = backup.restore(backup_path, storage_handler.vault_path())
        if not ok:
            ui.alert(self, self.t("backup.title"), msg, kind="negative")
            return False
        self.logout()
        return True
