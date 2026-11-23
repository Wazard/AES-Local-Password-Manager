"""Change the master password (re-keys the vault to a new Argon2id key)."""
import customtkinter as ctk

from core import password_strength
from UI import components as ui
from UI import theme as T


class ChangeMasterMixin:
    def show_change_master_screen(self):
        self.current_view = "changepw"
        ui.app_bar(self, back=self.show_dashboard, show_nav=True)
        # Master passwords are typed here: the form starts empty on every
        # visit and is wiped again on the way out.
        self.open_screen("changepw", self._build_change_master,
                         refresh=self._reset_change_master,
                         leave=self._reset_change_master)

    def _reset_change_master(self):
        cp = self._changepw
        for entry in (cp["current"], cp["new"], cp["confirm"]):
            entry.conceal()
            ui.set_text(entry, "")
        cp["meter"].reset(self.t("auth.requirement"))
        cp["match"].clear()
        cp["status"].clear()

    def _build_change_master(self):
        body = ui.page(self)
        ui.title(body, self.t("changepw.title")).pack(anchor="w")

        form = ctk.CTkFrame(body, fg_color="transparent")
        form.pack(fill="x", pady=(T.GAP_L, 0))

        def field(label_key, pady=(0, 0)):
            ui.field_label(form, self.t(label_key)).pack(anchor="w", pady=pady)
            row, entry = ui.secret_field(form, mono=False)
            row.pack(fill="x", pady=(4, 0))
            return entry

        current = field("changepw.current")
        new = field("changepw.new", pady=(T.GAP, 0))

        meter = ui.StrengthMeter(form)
        meter.pack(fill="x", pady=(6, 0))
        meter.reset(self.t("auth.requirement"))

        confirm = field("changepw.confirm", pady=(T.GAP, 0))
        match_line = ui.StatusLine(form)
        match_line.pack(anchor="w", pady=(6, 0))

        def on_new(_event=None):
            value = new.get()
            if not value:
                meter.reset(self.t("auth.requirement"))
            else:
                result = password_strength.evaluate(value)
                meter.set(result["score"], self.t("strength.%d" % result["score"]))
            on_confirm()

        def on_confirm(_event=None):
            typed = confirm.get()
            if not typed:
                match_line.clear()
            elif typed == new.get():
                match_line.show("✓ " + self.t("changepw.match"), "positive")
            else:
                match_line.show(self.t("changepw.mismatch"), "negative")

        new.bind("<KeyRelease>", on_new, add="+")
        confirm.bind("<KeyRelease>", on_confirm, add="+")

        status = ui.StatusLine(body, wraplength=420)
        status.pack(anchor="w", pady=(T.GAP, 0))

        def submit():
            if new.get() != confirm.get():
                status.show(self.t("changepw.mismatch"), "negative")
                return
            result = self.change_master(current.get(), new.get())
            if result == "wrong_current":
                status.show(self.t("changepw.wrong"), "negative")
            elif result == "weak":
                status.show(self.t("auth.weak"), "negative")
            elif result == "save_failed":
                status.show(self.t("modal.save_failed_msg"), "negative")
            elif result == "ok":
                status.show(self.t("changepw.success"), "positive")
                self.after(900, self.show_dashboard)

        bar = ui.footer(self)
        ui.default_button(self, ui.primary_button(
            bar, self.t("changepw.save"), submit, height=42)).pack(fill="x")
        self._changepw = {"current": current, "new": new, "confirm": confirm,
                          "meter": meter, "match": match_line, "status": status}
