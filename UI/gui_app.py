"""Secure Vault — main application window.

The screens live in dedicated mixins (UI/screen_*.py); this file wires them
together and owns shared state and the window/tray lifecycle.
"""
import os
import json
import customtkinter as ctk
from tkinter import messagebox

from core import encryption
from core import storage_handler
from core import storage_compression
from localization.language_manager import LanguageManager

from UI.theme import apply_theme
from UI.tray import TrayManager, TRAY_AVAILABLE
from UI.screen_auth import AuthMixin
from UI.screen_dashboard import DashboardMixin
from UI.screen_entry import EntryMixin
from UI.screen_generator import GeneratorMixin

apply_theme()


class PasswordManagerGUI(ctk.CTk, AuthMixin, DashboardMixin, EntryMixin, GeneratorMixin):
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
        self.view_mode = "grid"
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

        # Vault session
        self.master_password = ""
        self.vault_data = {}

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self.show_auth_screen()

    # --- Window lifecycle ---
    def _on_close(self):
        """Minimise to the Windows tray when the toggle is on; otherwise quit."""
        if self.minimize_to_tray.get() and TRAY_AVAILABLE:
            self.tray.hide()
        else:
            self.tray.stop()
            self.destroy()

    def logout(self):
        """Clear the decrypted session and return to the login screen."""
        self.master_password = ""
        self.vault_data = {}
        self.search_query = ""
        self.sort_mode = "name_asc"
        self.view_mode = "grid"
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
        }
        view_map[self.current_view]()

    def clear_screen(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)

    def save_vault(self):
        try:
            json_data = json.dumps(self.vault_data)
            compressed = storage_compression.compress_data(json_data)
            encrypted = encryption.encrypt_data(compressed, self.master_password)
            storage_handler.write_vault(encrypted)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}")
            return False
