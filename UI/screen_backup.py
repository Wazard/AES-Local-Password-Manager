"""Screen to back up the encrypted vault to OneDrive or a custom folder.

Creating/removing the symlink needs admin rights; when the app isn't elevated
we relaunch the single operation via UAC and poll for its result.
"""
import os
import shutil
import customtkinter as ctk
from tkinter import filedialog

from core import backup, storage_handler, elevation
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

        if st["is_link"]:
            ctk.CTkLabel(card, text=self.t("backup.linked"), text_color=COLOR_SUCCESS,
                         font=(FONT_FAMILY, 13, "bold")).pack(anchor="w", padx=20, pady=(18, 0))
            ctk.CTkLabel(card, text=st["target"], text_color=COLOR_MUTED,
                         font=("Courier New", 11), wraplength=440,
                         justify="left").pack(anchor="w", padx=20, pady=(2, 12))
            ctk.CTkButton(card, text=self.t("backup.remove"), height=40,
                          fg_color=COLOR_DANGER, hover_color=COLOR_DANGER_HOVER,
                          command=self._do_remove_backup).pack(anchor="w", padx=20, pady=(0, 18))
        else:
            ctk.CTkLabel(card, text=self.t("backup.not_linked"), text_color=COLOR_MUTED,
                         font=(FONT_FAMILY, 13)).pack(anchor="w", padx=20, pady=(18, 14))

            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=(0, 18))
            if st["onedrive"]:
                ctk.CTkButton(row, text=self.t("backup.create"), height=46,
                              fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER,
                              command=lambda: self._create_at(st["onedrive"])
                              ).pack(side="left", expand=True, fill="x")
                ctk.CTkLabel(row, text=self.t("backup.or"), text_color=COLOR_MUTED,
                             font=(FONT_FAMILY, 12, "bold")).pack(side="left", padx=14)
            ctk.CTkButton(row, text=self.t("backup.choose"), height=46,
                          command=self._choose_custom).pack(side="left", expand=True, fill="x")

            if not st["onedrive"]:
                ctk.CTkLabel(card, text=self.t("backup.no_onedrive"), text_color=COLOR_MUTED,
                             wraplength=440, justify="left").pack(anchor="w", padx=20, pady=(0, 14))

        msg = getattr(self, "_backup_msg", "")
        if msg:
            ctk.CTkLabel(self.container, text=msg, text_color=COLOR_MUTED,
                         wraplength=460, justify="left").pack(padx=34, pady=(16, 0))

        ctk.CTkLabel(self.container, text=self.t("backup.hint"), text_color=COLOR_MUTED,
                     font=(FONT_FAMILY, 11), wraplength=460,
                     justify="left").pack(padx=34, pady=18)

    # --- actions ---
    def _vault_abs(self):
        return os.path.abspath(storage_handler.VAULT_FILE)

    def _choose_custom(self):
        folder = filedialog.askdirectory(title=self.t("backup.choose"))
        if folder:
            self._create_at(folder)

    def _create_at(self, base_dir):
        vault = self._vault_abs()
        # Admin or Developer Mode: create the link directly, in-process.
        if elevation.is_admin() or backup.can_symlink():
            ok, msg, _ = backup.create_link(vault, base_dir)
            self._backup_msg = msg
            self.show_backup_screen()
            return
        # Otherwise: move the vault, then create the link via an elevated
        # `mklink` — this is what shows the UAC "allow changes?" prompt.
        ok, info = backup.prepare_link(vault, base_dir)
        if not ok:
            self._backup_msg = info
            self.show_backup_screen()
            return
        target = info
        if not elevation.run_elevated_cmd('mklink "%s" "%s"' % (vault, target)):
            backup.rollback_link(vault, target)  # UAC declined / failed to start
            self._backup_msg = self.t("backup.denied")
            self.show_backup_screen()
            return
        self._backup_msg = self.t("backup.waiting")
        self.show_backup_screen()
        self._poll_link(target)

    def _poll_link(self, target, tries=0):
        if os.path.islink(self._vault_abs()):
            self._backup_msg = ""
            if self.current_view == "backup":
                self.show_backup_screen()
            return
        if tries < 30 and self.current_view == "backup":  # ~15s
            self.after(500, lambda: self._poll_link(target, tries + 1))
        elif self.current_view == "backup":
            backup.rollback_link(self._vault_abs(), target)
            self._backup_msg = self.t("backup.denied")
            self.show_backup_screen()

    def _do_remove_backup(self):
        vault = self._vault_abs()
        if not os.path.islink(vault):
            _, msg, _ = backup.remove_link(vault)
            self._backup_msg = msg
            self.show_backup_screen()
            return
        target = os.path.realpath(vault)
        ok, msg, reason = backup.remove_link(vault)
        if ok:
            self._backup_msg = msg
            self.show_backup_screen()
            return
        if reason == "permission" and not elevation.is_admin() and \
                elevation.run_elevated_cmd('del "%s"' % vault):
            self._poll_unlink(target)
            return
        self._backup_msg = msg
        self.show_backup_screen()

    def _poll_unlink(self, target, tries=0):
        vault = self._vault_abs()
        if not os.path.lexists(vault):
            if os.path.exists(target) and not os.path.exists(vault):
                try:
                    shutil.copy2(target, vault)
                except OSError:
                    pass
            self._backup_msg = ""
            if self.current_view == "backup":
                self.show_backup_screen()
            return
        if tries < 30 and self.current_view == "backup":
            self.after(500, lambda: self._poll_unlink(target, tries + 1))
