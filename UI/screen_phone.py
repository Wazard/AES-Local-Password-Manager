"""iPhone: sync with the iOS app, or send it this vault, over the local network.

Only encrypted vault files travel (see core/phone_transfer.py); the phone
shows a code that has to be typed here. Sync applies what was changed on the
iPhone to this vault and sends the result back; Send replaces the iPhone's
vault (it asks first). Discovery and network work run off the Tk thread and
report back with `after`, so a slow network never freezes the window.
"""
import json
import threading
import customtkinter as ctk

from core import data_handler, encryption, phone_transfer, storage_compression, storage_handler
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

        # Sync is the everyday action: it keeps what was changed on the
        # iPhone. Sending replaces the iPhone's vault with this one.
        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x", pady=(T.GAP, 0))
        self._ph_sync = ui.default_button(
            self, ui.primary_button(buttons, self.t("phone.sync"), self._phone_sync))
        self._ph_sync.pack(side="left", expand=True, fill="x")
        self._ph_send = ui.secondary_button(buttons, self.t("phone.send"), self._phone_send)
        self._ph_send.pack(side="left", expand=True, fill="x", padx=(T.GAP_S, 0))
        self._ph_status = ui.StatusLine(body, wraplength=460)
        self._ph_status.pack(anchor="w", pady=(T.GAP_S, 0))

        ui.hint(body, self.t("phone.hint"), wraplength=460).pack(anchor="w", pady=(T.GAP_L, 0))

    def _refresh_phone(self):
        ui.set_text(self._ph_code, "")
        self._ph_status.clear()
        self._phone_busy(None)
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
            ui.focusable(ctk.CTkRadioButton(
                self._ph_list, text="%s  ·  %s" % (device["name"], device["host"]),
                variable=self._ph_target, value=value, font=T.font(T.S_BODY),
                radiobutton_width=18, radiobutton_height=18,
                command=lambda: ui.set_text(self._ph_address, ""))).pack(anchor="w", pady=3)

    # --- sending and syncing --------------------------------------------
    def _phone_request(self):
        """(host, port, code) from the form, or None after saying what's missing."""
        code = "".join(ch for ch in self._ph_code.get() if ch.isdigit())
        typed = self._ph_address.get().strip()
        if typed:
            host, port = typed, phone_transfer.PORT
        elif self._ph_target.get():
            host, _, port = self._ph_target.get().rpartition(":")
            port = int(port)
        else:
            self._ph_status.show(self.t("phone.need_target"), "negative")
            return None
        if len(code) != 6:
            self._ph_status.show(self.t("phone.need_code"), "negative")
            return None
        if not storage_handler.read_vault():
            self._ph_status.show(self.t("phone.err_novault"), "negative")
            return None
        return host, port, code

    def _phone_busy(self, button):
        """Disable both actions while one runs; `button` shows the progress."""
        for btn, key in ((self._ph_sync, "phone.sync"), (self._ph_send, "phone.send")):
            if btn is button:
                btn.configure(state="disabled",
                              text=self.t("phone.syncing" if btn is self._ph_sync else "phone.sending"))
            else:
                btn.configure(state="disabled" if button is not None else "normal",
                              text=self.t(key))

    def _phone_send(self):
        request = self._phone_request()
        if request is None:
            return
        host, port, code = request
        vault = storage_handler.read_vault()
        self._phone_busy(self._ph_send)
        self._ph_status.clear()

        def work():
            result = phone_transfer.send(host, vault, code, port=port)
            self.after(0, lambda: self._phone_done(result, host, self.t("phone.sent", device=host)))

        threading.Thread(target=work, daemon=True).start()

    def _phone_sync(self):
        request = self._phone_request()
        if request is None:
            return
        host, port, code = request
        self._phone_busy(self._ph_sync)
        self._ph_status.clear()
        report = {}

        def merge(phone_vault):
            # The vault belongs to the Tk thread: hand the merge over and wait.
            result = {}
            done = threading.Event()

            def on_tk():
                try:
                    result["merged"] = self._merge_phone_vault(phone_vault, report)
                except phone_transfer.TransferError as e:
                    result["error"] = e
                except Exception:
                    result["error"] = phone_transfer.TransferError("savefailed")
                finally:
                    done.set()

            self.after(0, on_tk)
            if not done.wait(timeout=15):
                raise phone_transfer.TransferError("noreply")
            if "error" in result:
                raise result["error"]
            return result["merged"]

        def work():
            result, phone = phone_transfer.sync(host, code, merge, port=port)
            self.after(0, lambda: self._phone_done(result, host, self._sync_summary(report, phone or host)))

        threading.Thread(target=work, daemon=True).start()

    def _merge_phone_vault(self, phone_vault, report):
        """Apply the iPhone's marked changes to this vault, save, and return
        the saved file to send back. Runs on the Tk thread."""
        try:
            payload = encryption.open_with_key(phone_vault, self.vault_key,
                                               self.vault_salt, self.vault_params)
            phone = json.loads(storage_compression.decompress_data(payload))
        except Exception:
            raise phone_transfer.TransferError("mismatch")
        changes = data_handler.merge_phone_changes(self.vault_data, phone, self.session.encrypt)
        report.update(changes)
        if any(changes.values()):
            # Saving also bumps the vault revision, so the dashboard redraws
            # the new accounts when it is shown next, and makes a backup.
            if not self._persist_vault():
                raise phone_transfer.TransferError("savefailed")
        return storage_handler.read_vault()

    def _sync_summary(self, report, device):
        n = sum(len(v) for v in report.values())
        return (self.t("phone.synced", device=device, n=n) if n
                else self.t("phone.synced_none", device=device))

    def _phone_done(self, result, host, success_text):
        if not self._ph_send.winfo_exists():
            return
        self._phone_busy(None)
        if result == "ok":
            ui.set_text(self._ph_code, "")
            self._ph_status.show(success_text, "positive")
            return
        key = {"badcode": "phone.err_badcode", "toolarge": "phone.err_toolarge",
               "notvault": "phone.err_notvault", "busy": "phone.err_busy",
               "unreachable": "phone.err_unreachable", "mismatch": "phone.err_mismatch",
               "locked": "phone.err_locked", "novault": "phone.err_phone_novault",
               "savefailed": "phone.err_savefailed"}.get(result, "phone.err_noreply")
        self._ph_status.show(self.t(key, host=host), "negative")
