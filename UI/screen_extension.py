"""Settings screen for the browser-extension autofill bridge."""
import webbrowser
import customtkinter as ctk

from UI.theme import (FONT_FAMILY, COLOR_BG_CARD, COLOR_SUCCESS, COLOR_MUTED,
                      COLOR_GOLD, COLOR_GOLD_HOVER, COLOR_CHARCOAL)
from UI.components import back_button, copy_button

# TODO: replace with your real add-on listing URL once published on AMO.
ADDON_URL = "https://addons.mozilla.org/firefox/addon/secure-vault-autofill/"


class ExtensionMixin:
    def show_extension_screen(self):
        self.current_view = "extension"
        self.clear_screen()
        back_button(self)
        ctk.CTkLabel(self.container, text=self.t("extension.title"),
                     font=(FONT_FAMILY, 22, "bold")).pack(pady=(0, 10))

        # Featured link to the published add-on.
        ctk.CTkButton(self.container, text=self.t("extension.get_addon"),
                      fg_color=COLOR_GOLD, hover_color=COLOR_GOLD_HOVER,
                      text_color=COLOR_CHARCOAL, height=36,
                      command=lambda: webbrowser.open(ADDON_URL)).pack(pady=(0, 14))

        card = ctk.CTkFrame(self.container, fg_color=COLOR_BG_CARD, corner_radius=12)
        card.pack(fill="x", padx=30)

        # Enable toggle + status
        ctk.CTkCheckBox(card, text=self.t("extension.enable"),
                        variable=self.ext_enabled, command=self.toggle_extension
                        ).pack(anchor="w", padx=16, pady=(16, 6))
        status_on = self.autofill_server is not None and self.autofill_server.running
        ctk.CTkLabel(card,
                     text=self.t("extension.running") if status_on else self.t("extension.stopped"),
                     text_color=COLOR_SUCCESS if status_on else COLOR_MUTED,
                     font=(FONT_FAMILY, 12)).pack(anchor="w", padx=16, pady=(0, 10))

        # Port
        ctk.CTkLabel(card, text=self.t("extension.port"),
                     font=(FONT_FAMILY, 12, "bold")).pack(anchor="w", padx=16)
        ctk.CTkLabel(card, text=str(self.ext_port), font=("Courier New", 13),
                     text_color=COLOR_MUTED).pack(anchor="w", padx=16, pady=(0, 10))

        # Pairing token (read-only) + copy
        ctk.CTkLabel(card, text=self.t("extension.token"),
                     font=(FONT_FAMILY, 12, "bold")).pack(anchor="w", padx=16)
        token_row = ctk.CTkFrame(card, fg_color="transparent")
        token_row.pack(fill="x", padx=16, pady=(2, 10))
        token = self.get_extension_token()
        token_entry = ctk.CTkEntry(token_row, font=("Courier New", 13), height=34)
        token_entry.insert(0, token)
        token_entry.configure(state="readonly")
        token_entry.pack(side="left", fill="x", expand=True)
        copy_button(self, token_row, lambda: token).pack(side="right", padx=(8, 0))

        ctk.CTkButton(card, text=self.t("extension.regenerate"), height=34,
                      command=self.regenerate_token).pack(anchor="w", padx=16, pady=(0, 16))

        # Browser launch (securevault:// protocol) so the extension can open/focus the app.
        launch_card = ctk.CTkFrame(self.container, fg_color=COLOR_BG_CARD, corner_radius=12)
        launch_card.pack(fill="x", padx=30, pady=(14, 0))
        ctk.CTkCheckBox(launch_card, text=self.t("extension.launch"),
                        variable=self.protocol_enabled, command=self.toggle_protocol
                        ).pack(anchor="w", padx=16, pady=16)

        ctk.CTkLabel(self.container, text=self.t("extension.hint", port=self.ext_port),
                     font=(FONT_FAMILY, 11), text_color=COLOR_MUTED,
                     wraplength=420, justify="left").pack(padx=34, pady=(14, 0), anchor="w")
        ctk.CTkLabel(self.container, text=self.t("extension.launch_hint"),
                     font=(FONT_FAMILY, 11), text_color=COLOR_MUTED,
                     wraplength=420, justify="left").pack(padx=34, pady=(8, 16), anchor="w")
