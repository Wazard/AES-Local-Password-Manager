"""Secure Vault — main application window.

The screens live in dedicated mixins (UI/screen_*.py); this file wires them
together and owns shared state and the window/tray lifecycle.
"""
import os
import time
import json
import threading
import customtkinter as ctk
from tkinter import messagebox

from core import encryption
from core import storage_handler
from core import storage_compression
from core import data_handler
from core import app_config
from core import password_generator
from core import protocol_handler
from core.autofill_server import AutofillServer
from core.single_instance import ControlServer
from core.session_crypto import SessionCrypto
from localization.language_manager import LanguageManager

from UI.theme import apply_theme
from UI.tray import TrayManager, TRAY_AVAILABLE
from UI.screen_auth import AuthMixin
from UI.screen_dashboard import DashboardMixin
from UI.screen_entry import EntryMixin
from UI.screen_generator import GeneratorMixin
from UI.screen_extension import ExtensionMixin
from UI.screen_backup import BackupMixin

apply_theme()

AUTO_LOCK_MS = 5 * 60 * 1000      # re-lock after 5 minutes of inactivity
CLIPBOARD_CLEAR_MS = 25 * 1000    # wipe copied secrets from the clipboard


class PasswordManagerGUI(ctk.CTk, AuthMixin, DashboardMixin, EntryMixin,
                         GeneratorMixin, ExtensionMixin, BackupMixin):
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
        self.geometry("520x600")
        self.minsize(460, 520)

        # System tray
        self._icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        self.minimize_to_tray = ctk.BooleanVar(value=False)
        self.tray = TrayManager(self, self._icon_path, self.t)
        try:
            self.iconbitmap(self._icon_path)
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Browser-extension autofill bridge
        self.ext_config = app_config.load()
        self.ext_port = self.ext_config.get("port", app_config.DEFAULT_PORT)
        self.ext_enabled = ctk.BooleanVar(value=self.ext_config.get("enabled", False))
        self.autofill_server = None
        if self.ext_enabled.get():
            self._start_autofill()

        # Single-instance control channel + securevault:// launch handler
        self._control = None
        self.protocol_enabled = ctk.BooleanVar(value=protocol_handler.is_registered())

        # Vault session — only the derived key is kept (never the master
        # password), and passwords are held encrypted with a per-session key.
        self.vault_key = None
        self.vault_salt = None
        self.vault_params = None
        self.vault_data = {}
        self.session = SessionCrypto()

        # Auto-lock on inactivity
        self._idle_after = None
        self.bind_all("<Key>", self._on_activity, add="+")
        self.bind_all("<ButtonPress>", self._on_activity, add="+")

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self.show_auth_screen()

    # --- Auto-lock ---
    def _on_activity(self, _event=None):
        if self.logged_in:
            self._reset_idle_timer()

    def _reset_idle_timer(self):
        if self._idle_after is not None:
            try:
                self.after_cancel(self._idle_after)
            except Exception:
                pass
        self._idle_after = self.after(AUTO_LOCK_MS, self._auto_lock)

    def _auto_lock(self):
        if self.logged_in:
            self.logout()

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

    # --- Single-instance / launch handling ---
    def start_control_server(self):
        self._control = ControlServer(lambda: self.after(0, self._restore_window))
        try:
            self._control.start()
        except Exception:
            self._control = None  # focus-on-relaunch unavailable; app still runs

    def toggle_protocol(self):
        try:
            if self.protocol_enabled.get():
                protocol_handler.register()
            else:
                protocol_handler.unregister()
        except Exception as e:
            messagebox.showerror("Browser launch", f"Could not update launcher: {e}")
            self.protocol_enabled.set(protocol_handler.is_registered())
        if self.current_view == "extension":
            self.show_extension_screen()

    def _start_autofill(self):
        token = self.get_extension_token()
        self.autofill_server = AutofillServer(
            "127.0.0.1", self.ext_port, token,
            self._autofill_unlocked, self._autofill_lookup,
            self._autofill_add, self._autofill_generate)
        try:
            self.autofill_server.start()
        except Exception as e:
            self.autofill_server = None
            messagebox.showerror("Extension", f"Could not start local server: {e}")

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

    def logout(self):
        """Clear the decrypted session (key + vault) and return to login."""
        if self._idle_after is not None:
            try:
                self.after_cancel(self._idle_after)
            except Exception:
                pass
            self._idle_after = None
        self.vault_key = None
        self.vault_salt = None
        self.vault_params = None
        self.vault_data = {}
        self.session.rotate()
        self.search_query = ""
        self.sort_mode = "name_asc"
        self.view_mode = "list"
        self.logged_in = False
        self.show_auth_screen()

    # --- Shared helpers ---
    def t(self, key, **kwargs):
        """Translation helper."""
        return self.lang_manager.get_text(key, self.current_lang, **kwargs)

    def change_language(self, new_lang):
        """Refresh the current screen with the new language."""
        self.current_lang = new_lang
        view_map = {
            "auth": self.show_auth_screen,
            "dashboard": self.show_dashboard,
            "add": lambda: self.show_add_screen(),
            "modify": lambda: self.show_add_screen(self.active_service),
            "details": lambda: self.show_details(self.active_service),
            "generator": self.show_gen_pass_screen,
            "extension": self.show_extension_screen,
            "backup": self.show_backup_screen,
        }
        view_map[self.current_view]()

    def clear_screen(self):
        for widget in self.container.winfo_children():
            widget.destroy()

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
            return True
        except Exception:
            return False
        finally:
            plain = None

    def save_vault(self):
        ok = self._persist_vault()
        if not ok:
            messagebox.showerror("Error", "Save failed.")
        return ok
