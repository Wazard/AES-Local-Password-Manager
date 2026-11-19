"""Backup screen: where the dated copies go, and restoring one.

Backups are plain encrypted copies (see core/backup.py), so this screen only
ever moves files around — no elevation, no symlinks, nothing that can leave the
vault in a half-configured state.
"""
import os
import time
import customtkinter as ctk
from tkinter import filedialog

from core import backup, storage_handler
from UI import components as ui
from UI import theme as T


class BackupMixin:
    def show_backup_screen(self):
        self.current_view = "backup"
        ui.app_bar(self, back=self.show_dashboard, show_nav=True)
        self.open_screen("backup", self._build_backup, refresh=self._refresh_backup)

    def _build_backup(self):
        body = ui.page(self)
        ui.title(body, self.t("backup.title")).pack(anchor="w")

        card = self._bk_card = ui.card(body)
        card.pack(fill="x", pady=(T.GAP_L, 0))
        ui.field_label(card, self.t("backup.folder_label")).pack(
            anchor="w", padx=T.PAD_CARD, pady=(T.PAD_CARD, 0))
        self._bk_folder = ctk.CTkLabel(card, text="", text_color=T.TEXT,
                                       font=T.mono(T.S_SMALL), wraplength=420,
                                       justify="left")
        self._bk_folder.pack(anchor="w", padx=T.PAD_CARD, pady=(2, T.GAP))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=T.PAD_CARD, pady=(0, T.PAD_CARD))
        ui.primary_button(row, self.t("backup.now"), self._backup_now).pack(
            side="left", expand=True, fill="x")
        ui.secondary_button(row, self.t("backup.choose"), self._choose_folder).pack(
            side="left", expand=True, fill="x", padx=(T.GAP_S, 0))

        self._bk_status = ui.StatusLine(body, wraplength=440)  # shown when there is news

        header = ctk.CTkFrame(body, fg_color="transparent")
        header.pack(fill="x", pady=(T.GAP_L, T.GAP_S))
        self._bk_heading = ui.heading(header, "")
        self._bk_heading.pack(anchor="w")

        self._bk_listing = ctk.CTkScrollableFrame(body, fg_color="transparent")
        self._bk_listing.pack(fill="both", expand=True)
        self._bk_rows = {}   # (path, size) -> row; every save adds a backup,
        self._bk_shown = []  # so rows are kept and only new ones are drawn

        ui.hint(body, self.t("backup.hint"), wraplength=440).pack(
            anchor="w", pady=(T.GAP, T.GAP_L))

    def _refresh_backup(self):
        folder = backup.backup_dir()
        backups = backup.list_backups(folder)
        self._bk_folder.configure(text=folder)

        msg = getattr(self, "_backup_msg", "")
        if msg:
            self._bk_status.show(msg, "negative" if msg == self.t("backup.failed")
                                 else "positive")
            self._bk_status.pack(anchor="w", pady=(T.GAP, 0), after=self._bk_card)
        else:
            self._bk_status.pack_forget()

        self._bk_heading.configure(text=self.t("backup.count", count=len(backups))
                                   if backups else self.t("backup.none"))

        keys = [(entry["path"], entry["size"]) for entry in backups]
        for key in set(self._bk_rows) - set(keys):
            row = self._bk_rows.pop(key)
            if row in self._bk_shown:
                self._bk_shown.remove(row)
            row.destroy()
        wanted = []
        for key, entry in zip(keys, backups):
            if key not in self._bk_rows:
                self._bk_rows[key] = self._backup_row(self._bk_listing, entry)
            wanted.append(self._bk_rows[key])
        self._bk_shown = ui.repack(self._bk_shown, wanted, fill="x", pady=3, padx=2)

    def _backup_row(self, parent, entry):
        row = ui.card(parent)

        ui.ghost_button(row, self.t("backup.delete"), lambda: self._delete(entry),
                        width=64, height=30, text_color=T.NEGATIVE).pack(
                            side="right", padx=(0, T.GAP_S))
        ui.secondary_button(row, self.t("backup.restore"), lambda: self._restore(entry),
                            width=78, height=30,
                            font=T.font(T.S_LABEL, "bold")).pack(side="right", padx=T.GAP_S)

        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True, padx=(T.GAP, 0), pady=T.GAP_S)
        ctk.CTkLabel(text, text=self._when(entry["when"]), font=T.font(T.S_BODY),
                     text_color=T.TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(text, text="%s · %.1f KB" % (entry["name"], entry["size"] / 1024.0),
                     font=T.mono(10), text_color=T.TEXT_MUTED,
                     anchor="w").pack(anchor="w")
        return row

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
        def go():
            self._backup_msg = ""
            # Sends the user back to the login screen: the restored copy may
            # have a different master password from the session open now.
            self.restore_backup(entry["path"])

        ui.confirm(self, self.t("backup.restore"),
                   self.t("backup.restore_confirm", when=self._when(entry["when"])),
                   go, yes_label=self.t("backup.restore"), danger=False)

    def _delete(self, entry):
        def go():
            backup.delete_backup(entry["path"])
            self.show_backup_screen()

        ui.confirm(self, self.t("backup.delete"),
                   self.t("backup.delete_confirm", when=self._when(entry["when"])),
                   go, yes_label=self.t("modal.delete"))
