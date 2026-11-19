"""Send to iPhone: hands the vault file to the iOS app over the local network.

Only the encrypted file on disk travels (see core/phone_transfer.py); the
phone shows a code that has to be typed here, and asks before it replaces
anything. Discovery and sending run off the Tk thread and report back with
`after`, so a slow network never freezes the window.
"""
import threading
import customtkinter as ctk

from core import phone_transfer, storage_handler
from UI import components as ui
from UI import theme as T


class PhoneMixin:
    def show_phone_screen(self):
        self.current_view = "phone"
        ui.app_bar(self, back=self.show_dashboard, show_nav=True)
        self.open_screen("phone", self._build_phone, refresh=self._refresh_phone,
                         leave=self._leave_phone)

    def _build_phone(self):
        # Scrolls, so the form still fits a window shrunk to its minimum size.
        body = ctk.CTkFrame(ui.page(self, scroll=True), fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8)
        ui.title(body, self.t("phone.title")).pack(anchor="w")
        ui.hint(body, self.t("phone.intro"), wraplength=460).pack(anchor="w", pady=(T.GAP_S, 0))

        card = ui.card(body)
        card.pack(fill="x", pady=(T.GAP_L, 0))
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=T.PAD_CARD, pady=(T.PAD_CARD, 0))
        ui.heading(head, self.t("phone.devices")).pack(side="left")
        self._ph_search_btn = ui.ghost_button(head, self.t("phone.search_again"),
                                              self._phone_discover, width=120)
        self._ph_search_btn.pack(side="right")

        self._ph_list = ctk.CTkFrame(card, fg_color="transparent")
        self._ph_list.pack(fill="x", padx=T.PAD_CARD, pady=(T.GAP_S, 0))
        self._ph_target = ctk.StringVar(value="")

        ui.field_label(card, self.t("phone.address")).pack(
            anchor="w", padx=T.PAD_CARD, pady=(T.GAP, 0))
        self._ph_address = ui.text_field(card, placeholder="192.168.1.20", mono=True)
        self._ph_address.pack(fill="x", padx=T.PAD_CARD, pady=(4, T.PAD_CARD))
        # Typing an address overrides whichever iPhone was picked in the list.
        self._ph_address.bind("<KeyRelease>", lambda _e: self._ph_address.get().strip()
                              and self._ph_target.set(""))

        ui.field_label(body, self.t("phone.code")).pack(anchor="w", pady=(T.GAP_L, 0))
        self._ph_code = ui.text_field(body, placeholder="000 000", mono=True)
        self._ph_code.pack(fill="x", pady=(4, 0))
        self._ph_code.bind("<Return>", lambda _e: self._phone_send())

        self._ph_send = ui.primary_button(body, self.t("phone.send"), self._phone_send)
        self._ph_send.pack(fill="x", pady=(T.GAP, 0))
        self._ph_status = ui.StatusLine(body, wraplength=460)
        self._ph_status.pack(anchor="w", pady=(T.GAP_S, 0))

        ui.hint(body, self.t("phone.hint"), wraplength=460).pack(anchor="w", pady=(T.GAP_L, 0))

    def _refresh_phone(self):
        ui.set_text(self._ph_code, "")
        self._ph_status.clear()
        self._ph_send.configure(state="normal", text=self.t("phone.send"))
        self._phone_discover()

    def _leave_phone(self):
        ui.set_text(self._ph_code, "")

    # --- finding iPhones -------------------------------------------------
    def _phone_discover(self):
        self._ph_search_btn.configure(state="disabled")
        self._phone_show_devices(None)

        def work():
            try:
                found = phone_transfer.discover()
            except Exception:
                found = []
            self.after(0, lambda: self._phone_found(found))

        threading.Thread(target=work, daemon=True).start()

    def _phone_found(self, found):
        if not self._ph_list.winfo_exists():
            return
        self._ph_search_btn.configure(state="normal")
        self._phone_show_devices(found)

    def _phone_show_devices(self, found):
        """`found` is None while searching."""
        for widget in self._ph_list.winfo_children():
            widget.destroy()
        if found is None:
            ui.hint(self._ph_list, self.t("phone.searching")).pack(anchor="w")
            return
        if not found:
            ui.hint(self._ph_list, self.t("phone.none_found"), wraplength=420).pack(anchor="w")
            self._ph_target.set("")
            return
        hosts = ["%s:%d" % (d["host"], d["port"]) for d in found]
        if self._ph_target.get() not in hosts and not self._ph_address.get().strip():
            self._ph_target.set(hosts[0])
        for device, value in zip(found, hosts):
            ctk.CTkRadioButton(
                self._ph_list, text="%s  ·  %s" % (device["name"], device["host"]),
                variable=self._ph_target, value=value, font=T.font(T.S_BODY),
                radiobutton_width=18, radiobutton_height=18,
                command=lambda: ui.set_text(self._ph_address, "")).pack(anchor="w", pady=3)

    # --- sending ---------------------------------------------------------
    def _phone_send(self):
        code = "".join(ch for ch in self._ph_code.get() if ch.isdigit())
        typed = self._ph_address.get().strip()
        if typed:
            host, port = typed, phone_transfer.PORT
        elif self._ph_target.get():
            host, _, port = self._ph_target.get().rpartition(":")
            port = int(port)
        else:
            self._ph_status.show(self.t("phone.need_target"), "negative")
            return
        if len(code) != 6:
            self._ph_status.show(self.t("phone.need_code"), "negative")
            return
        vault = storage_handler.read_vault()
        if not vault:
            self._ph_status.show(self.t("phone.err_novault"), "negative")
            return

        self._ph_send.configure(state="disabled", text=self.t("phone.sending"))
        self._ph_status.clear()

        def work():
            result = phone_transfer.send(host, vault, code, port=port)
            self.after(0, lambda: self._phone_sent(result, host))

        threading.Thread(target=work, daemon=True).start()

    def _phone_sent(self, result, host):
        if not self._ph_send.winfo_exists():
            return
        self._ph_send.configure(state="normal", text=self.t("phone.send"))
        if result == "ok":
            ui.set_text(self._ph_code, "")
            self._ph_status.show(self.t("phone.sent", device=host), "positive")
            return
        key = {"badcode": "phone.err_badcode", "toolarge": "phone.err_toolarge",
               "notvault": "phone.err_notvault", "busy": "phone.err_busy",
               "unreachable": "phone.err_unreachable"}.get(result, "phone.err_noreply")
        self._ph_status.show(self.t(key, host=host), "negative")
