"""Screen to back up the encrypted vault to OneDrive or a custom folder.

Creating/removing the symlink needs admin rights; when the app isn't elevated
we relaunch the single operation via UAC and poll for its result.
"""
import os
import shutil
import customtkinter as ctk
from tkinter import filedialog

from core import backup, storage_handler, elevation
from UI import components as ui
from UI import theme as T

POLL_TRIES = 30          # 30 x 500ms = ~15s, the UAC prompt's patience
POLL_INTERVAL_MS = 500


class BackupMixin:
    def show_backup_screen(self):
        self.current_view = "backup"
        self.clear_screen()
        ui.app_bar(self, back=self.show_dashboard, show_nav=True)

        body = ui.page(self, scroll=True)
        ui.title(body, self.t("backup.title")).pack(anchor="w", padx=8)

        st = backup.status(storage_handler.VAULT_FILE)
        card = ui.card(body)
        card.pack(fill="x", pady=(T.GAP_L, 0), padx=8)

        if st["is_link"]:
            ui.status_dot(card, self.t("backup.linked"), True).pack(
                anchor="w", padx=T.PAD_CARD, pady=(T.PAD_CARD, T.GAP))
            ui.field_label(card, self.t("backup.path_label")).pack(
                anchor="w", padx=T.PAD_CARD)
            ctk.CTkLabel(card, text=st["target"], text_color=T.TEXT,
                         font=T.mono(T.S_SMALL), wraplength=400,
                         justify="left").pack(anchor="w", padx=T.PAD_CARD, pady=(2, T.GAP))
            ui.danger_button(card, self.t("backup.remove"), self._do_remove_backup,
                             width=180).pack(anchor="w", padx=T.PAD_CARD,
                                             pady=(0, T.PAD_CARD))
        else:
            ui.status_dot(card, self.t("backup.not_linked"), False).pack(
                anchor="w", padx=T.PAD_CARD, pady=(T.PAD_CARD, T.GAP))

            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=T.PAD_CARD, pady=(0, T.PAD_CARD))
            if st["onedrive"]:
                ui.primary_button(row, self.t("backup.create"),
                                  lambda: self._create_at(st["onedrive"]),
                                  height=42).pack(fill="x")
                ctk.CTkLabel(row, text=self.t("backup.or"), text_color=T.TEXT_MUTED,
                             font=T.font(T.S_SMALL, "bold")).pack(pady=4)
            ui.secondary_button(row, self.t("backup.choose"), self._choose_custom,
                                height=42).pack(fill="x")

            if not st["onedrive"]:
                ui.hint(card, self.t("backup.no_onedrive"), wraplength=400).pack(
                    anchor="w", padx=T.PAD_CARD, pady=(0, T.PAD_CARD))

        # Pending UAC elevation: a real progress state rather than a grey line.
        self._backup_progress = None
        self._backup_wait_label = None
        if getattr(self, "_backup_waiting", False):
            pending = ctk.CTkFrame(body, fg_color="transparent")
            pending.pack(fill="x", pady=(T.GAP, 0), padx=8)
            self._backup_wait_label = ctk.CTkLabel(
                pending, text=self.t("backup.waiting_n", n=POLL_TRIES // 2),
                font=T.font(T.S_LABEL), text_color=T.TEXT_SECONDARY)
            self._backup_wait_label.pack(anchor="w", pady=(0, 6))
            self._backup_progress = ctk.CTkProgressBar(
                pending, height=5, corner_radius=3, progress_color=T.PRIMARY)
            self._backup_progress.set(0)
            self._backup_progress.pack(fill="x")

        msg = getattr(self, "_backup_msg", "")
        if msg:
            status = ui.StatusLine(body, wraplength=420)
            status.pack(anchor="w", pady=(T.GAP, 0), padx=8)
            status.show(msg, "negative" if msg == self.t("backup.denied") else "muted")

        ui.hint(body, self.t("backup.hint"), wraplength=440).pack(
            anchor="w", padx=8, pady=(T.GAP_L, T.GAP_L))

    def _set_wait_progress(self, tries):
        """Updates the pending UI in place instead of redrawing the screen."""
        remaining = max(int((POLL_TRIES - tries) * POLL_INTERVAL_MS / 1000), 0)
        if self._backup_progress is not None and self._backup_progress.winfo_exists():
            self._backup_progress.set(min(tries / POLL_TRIES, 1.0))
        if self._backup_wait_label is not None and self._backup_wait_label.winfo_exists():
            self._backup_wait_label.configure(
                text=self.t("backup.waiting_n", n=remaining))

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
            self._backup_msg = "" if ok else msg
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
        self._backup_msg = ""
        self._backup_waiting = True
        self.show_backup_screen()
        self._poll_link(target)

    def _poll_link(self, target, tries=0):
        if os.path.islink(self._vault_abs()):
            self._backup_msg = ""
            self._backup_waiting = False
            if self.current_view == "backup":
                self.show_backup_screen()
            return
        if tries < POLL_TRIES and self.current_view == "backup":
            self._set_wait_progress(tries)
            self.after(POLL_INTERVAL_MS, lambda: self._poll_link(target, tries + 1))
        elif self.current_view == "backup":
            backup.rollback_link(self._vault_abs(), target)
            self._backup_waiting = False
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
            self._backup_msg = ""
            self.show_backup_screen()
            return
        if reason == "permission" and not elevation.is_admin() and \
                elevation.run_elevated_cmd('del "%s"' % vault):
            self._backup_waiting = True
            self._backup_msg = ""
            self.show_backup_screen()
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
            self._backup_waiting = False
            if self.current_view == "backup":
                self.show_backup_screen()
            return
        if tries < POLL_TRIES and self.current_view == "backup":
            self._set_wait_progress(tries)
            self.after(POLL_INTERVAL_MS, lambda: self._poll_unlink(target, tries + 1))
        elif self.current_view == "backup":
            self._backup_waiting = False
            self._backup_msg = self.t("backup.denied")
            self.show_backup_screen()
