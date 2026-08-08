"""Backup screen: where the dated copies go, and restoring one.

Backups are plain encrypted copies (see core/backup.py), so this screen only
ever moves files around — no elevation, no symlinks, nothing that can leave the
vault in a half-configured state.
"""
import os
import time
import customtkinter as ctk
from tkinter import filedialog, messagebox

from core import backup, storage_handler
from UI.theme import (FONT_FAMILY, COLOR_BG_CARD, COLOR_CARD_HOVER, COLOR_SUCCESS,
                      COLOR_SUCCESS_HOVER, COLOR_DANGER, COLOR_DANGER_HOVER, COLOR_MUTED)
from UI.components import back_button


class BackupMixin:
    def show_backup_screen(self):
        self.current_view = "backup"
        self.clear_screen()
        back_button(self)
        ctk.CTkLabel(self.container, text=self.t("backup.title"),
                     font=(FONT_FAMILY, 22, "bold")).pack(pady=(0, 12))

        folder = backup.backup_dir()
        backups = backup.list_backups(folder)

        card = ctk.CTkFrame(self.container, fg_color=COLOR_BG_CARD, corner_radius=12)
        card.pack(fill="x", padx=24)
        ctk.CTkLabel(card, text=self.t("backup.folder_label"), font=(FONT_FAMILY, 13, "bold"),
                     text_color=COLOR_SUCCESS).pack(anchor="w", padx=18, pady=(14, 0))
        ctk.CTkLabel(card, text=folder, text_color=COLOR_MUTED, font=("Courier New", 11),
                     wraplength=430, justify="left").pack(anchor="w", padx=18, pady=(2, 10))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(0, 16))
        ctk.CTkButton(row, text=self.t("backup.now"), height=38,
                      fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER,
                      command=self._backup_now).pack(side="left", expand=True, fill="x")
        ctk.CTkButton(row, text=self.t("backup.choose"), height=38,
                      command=self._choose_folder).pack(side="left", expand=True,
                                                        fill="x", padx=(10, 0))

        msg = getattr(self, "_backup_msg", "")
        if msg:
            ctk.CTkLabel(self.container, text=msg, text_color=COLOR_MUTED, wraplength=460,
                         justify="left").pack(padx=26, pady=(12, 0))

        ctk.CTkLabel(self.container,
                     text=self.t("backup.count", count=len(backups)) if backups
                     else self.t("backup.none"),
                     font=(FONT_FAMILY, 13, "bold")).pack(anchor="w", padx=26, pady=(16, 4))

        listing = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        listing.pack(fill="both", expand=True, padx=20, pady=(0, 6))
        for entry in backups:
            self._backup_row(listing, entry)

        ctk.CTkLabel(self.container, text=self.t("backup.hint"), text_color=COLOR_MUTED,
                     font=(FONT_FAMILY, 11), wraplength=460,
                     justify="left").pack(padx=26, pady=(0, 14))

    def _backup_row(self, parent, entry):
        row = ctk.CTkFrame(parent, fg_color=COLOR_BG_CARD, corner_radius=10)
        row.pack(fill="x", pady=4)

        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True, padx=(14, 6), pady=8)
        ctk.CTkLabel(text, text=self._when(entry["when"]), font=(FONT_FAMILY, 13),
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(text, text="%s · %.1f KB" % (entry["name"], entry["size"] / 1024.0),
                     font=("Courier New", 10), text_color=COLOR_MUTED,
                     anchor="w").pack(anchor="w")

        ctk.CTkButton(row, text=self.t("backup.delete"), width=70, height=30,
                      fg_color=COLOR_BG_CARD, hover_color=COLOR_CARD_HOVER,
                      text_color=COLOR_DANGER,
                      command=lambda: self._delete(entry)).pack(side="right", padx=(0, 10))
        ctk.CTkButton(row, text=self.t("backup.restore"), width=80, height=30,
                      fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER,
                      command=lambda: self._restore(entry)).pack(side="right", padx=8)

    @staticmethod
    def _when(timestamp):
        return time.strftime("%d/%m/%Y %H:%M", time.localtime(timestamp))

    # --- actions ---
    def _backup_now(self):
        path = backup.make_backup(storage_handler.vault_path())
        self._backup_msg = (self.t("backup.done", name=os.path.basename(path)) if path
                            else self.t("backup.failed"))
        self.show_backup_screen()

    def _choose_folder(self):
        folder = filedialog.askdirectory(title=self.t("backup.choose"))
        if not folder:
            return
        backup.set_backup_dir(folder)
        self._backup_msg = ""
        self.show_backup_screen()

    def _restore(self, entry):
        if not messagebox.askyesno(self.t("backup.title"),
                                   self.t("backup.restore_confirm",
                                          when=self._when(entry["when"]))):
            return
        self._backup_msg = ""
        # Sends the user back to the login screen: the restored copy may have a
        # different master password from the session that is open now.
        self.restore_backup(entry["path"])

    def _delete(self, entry):
        if not messagebox.askyesno(self.t("backup.title"),
                                   self.t("backup.delete_confirm",
                                          when=self._when(entry["when"]))):
            return
        backup.delete_backup(entry["path"])
        self.show_backup_screen()
