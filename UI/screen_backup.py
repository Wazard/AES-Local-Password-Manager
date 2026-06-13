"""Screen to back up the encrypted vault to OneDrive via a symlink."""
import customtkinter as ctk

from core import backup, storage_handler
from UI.theme import (FONT_FAMILY, COLOR_BG_CARD, COLOR_SUCCESS, COLOR_SUCCESS_HOVER,
                      COLOR_DANGER, COLOR_DANGER_HOVER, COLOR_MUTED)
from UI.components import back_button


class BackupMixin:
    def show_backup_screen(self):
        self.current_view = "backup"
        self.clear_screen()
        back_button(self)
        ctk.CTkLabel(self.container, text=self.t("backup.title"),
                     font=(FONT_FAMILY, 22, "bold")).pack(pady=(0, 16))

        st = backup.status(storage_handler.VAULT_FILE)
        card = ctk.CTkFrame(self.container, fg_color=COLOR_BG_CARD, corner_radius=12)
        card.pack(fill="x", padx=30)

        if not st["onedrive"]:
            ctk.CTkLabel(card, text=self.t("backup.no_onedrive"), text_color=COLOR_MUTED,
                         wraplength=400, justify="left").pack(padx=16, pady=18)
        else:
            ctk.CTkLabel(card, text=self.t("backup.onedrive_found"),
                         font=(FONT_FAMILY, 12, "bold")).pack(anchor="w", padx=16, pady=(16, 0))
            ctk.CTkLabel(card, text=st["onedrive"], text_color=COLOR_MUTED,
                         wraplength=400, justify="left").pack(anchor="w", padx=16, pady=(0, 10))

            if st["is_link"]:
                ctk.CTkLabel(card, text=self.t("backup.linked"), text_color=COLOR_SUCCESS,
                             font=(FONT_FAMILY, 12, "bold")).pack(anchor="w", padx=16)
                ctk.CTkLabel(card, text=st["target"], text_color=COLOR_MUTED,
                             font=("Courier New", 11), wraplength=400,
                             justify="left").pack(anchor="w", padx=16, pady=(0, 10))
                ctk.CTkButton(card, text=self.t("backup.remove"), height=36,
                              fg_color=COLOR_DANGER, hover_color=COLOR_DANGER_HOVER,
                              command=self._do_remove_backup).pack(anchor="w", padx=16, pady=(0, 16))
            else:
                ctk.CTkLabel(card, text=self.t("backup.not_linked"), text_color=COLOR_MUTED
                             ).pack(anchor="w", padx=16, pady=(0, 8))
                ctk.CTkButton(card, text=self.t("backup.create"), height=36,
                              fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER,
                              command=self._do_create_backup).pack(anchor="w", padx=16, pady=(0, 16))

        msg = getattr(self, "_backup_msg", "")
        if msg:
            ctk.CTkLabel(self.container, text=msg, text_color=COLOR_MUTED,
                         wraplength=420, justify="left").pack(padx=34, pady=(14, 0))

        ctk.CTkLabel(self.container, text=self.t("backup.hint"), text_color=COLOR_MUTED,
                     font=(FONT_FAMILY, 11), wraplength=420,
                     justify="left").pack(padx=34, pady=16)

    def _do_create_backup(self):
        onedrive = backup.get_onedrive_dir()
        if not onedrive:
            return
        _ok, self._backup_msg = backup.create_link(storage_handler.VAULT_FILE, onedrive)
        self.show_backup_screen()

    def _do_remove_backup(self):
        _ok, self._backup_msg = backup.remove_link(storage_handler.VAULT_FILE)
        self.show_backup_screen()
