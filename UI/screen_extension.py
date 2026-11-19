"""Settings screen (autofill bridge, browser launch, anti-tamper)."""
import webbrowser
import customtkinter as ctk

from UI import components as ui
from UI import icons
from UI import theme as T

ADDON_URL = "https://addons.mozilla.org/en-US/firefox/addon/securevault/"


class ExtensionMixin:
    def show_extension_screen(self):
        self.current_view = "extension"
        self.clear_screen()
        ui.app_bar(self, back=self.show_dashboard, show_nav=True)

        body = ui.page(self, scroll=True)
        ui.title(body, self.t("extension.title")).pack(anchor="w", padx=8)

        ui.secondary_button(
            body, self.t("extension.get_addon"), lambda: webbrowser.open(ADDON_URL),
            image=icons.load_tinted("extension.png", 16, T.TEXT_SECONDARY),
            height=40).pack(fill="x", pady=(T.GAP, 0), padx=8)

        # --- Autofill bridge -------------------------------------------------
        bridge = ui.card(body)
        bridge.pack(fill="x", pady=(T.GAP, 0), padx=8)

        head = ctk.CTkFrame(bridge, fg_color="transparent")
        head.pack(fill="x", padx=T.PAD_CARD, pady=(T.PAD_CARD, 0))
        ui.heading(head, self.t("extension.section_bridge")).pack(side="left")
        running = self.autofill_server is not None and self.autofill_server.running
        ui.status_dot(head, self.t("extension.running") if running
                      else self.t("extension.stopped"), running).pack(side="right")

        ctk.CTkCheckBox(bridge, text=self.t("extension.enable"),
                        variable=self.ext_enabled, command=self.toggle_extension,
                        font=T.font(T.S_BODY), checkbox_width=18, checkbox_height=18
                        ).pack(anchor="w", padx=T.PAD_CARD, pady=(T.GAP, 0))
        ui.hint(bridge, self.t("extension.hint", port=self.ext_port),
                wraplength=420).pack(anchor="w", padx=T.PAD_CARD, pady=(6, T.GAP))

        ui.divider(bridge).pack(fill="x", padx=T.PAD_CARD)

        # Port + pairing token are what the extension needs to pair.
        pair = ctk.CTkFrame(bridge, fg_color="transparent")
        pair.pack(fill="x", padx=T.PAD_CARD, pady=(T.GAP, T.PAD_CARD))

        port_row = ctk.CTkFrame(pair, fg_color="transparent")
        port_row.pack(fill="x")
        ui.field_label(port_row, self.t("extension.port")).pack(side="left")
        ctk.CTkLabel(port_row, text=str(self.ext_port), font=T.mono(),
                     text_color=T.TEXT).pack(side="left", padx=(T.GAP_S, 0))

        ui.field_label(pair, self.t("extension.token")).pack(anchor="w", pady=(T.GAP, 0))
        token_row = ctk.CTkFrame(pair, fg_color="transparent")
        token_row.pack(fill="x", pady=(4, 0))
        token = self.get_extension_token()
        ui.text_field(token_row, value=token, readonly=True, mono=True).pack(
            side="left", fill="x", expand=True)
        ui.copy_button(self, token_row, lambda: token).pack(side="left", padx=(T.GAP_S, 0))

        ui.ghost_button(pair, self.t("extension.regenerate"), self.regenerate_token,
                        width=150, anchor="w").pack(anchor="w", pady=(T.GAP_S, 0))

        # --- Security --------------------------------------------------------
        guard = ui.card(body)
        guard.pack(fill="x", pady=(T.GAP_L, T.GAP_L), padx=8)
        ui.heading(guard, self.t("extension.section_security")).pack(
            anchor="w", padx=T.PAD_CARD, pady=(T.PAD_CARD, 0))
        ctk.CTkCheckBox(guard, text=self.t("extension.tamper"),
                        variable=self.tamper_enabled, command=self.toggle_tamper,
                        font=T.font(T.S_BODY), checkbox_width=18, checkbox_height=18
                        ).pack(anchor="w", padx=T.PAD_CARD, pady=(T.GAP, 0))
        ui.hint(guard, self.t("extension.tamper_hint"), wraplength=420).pack(
            anchor="w", padx=T.PAD_CARD, pady=(6, T.PAD_CARD))
