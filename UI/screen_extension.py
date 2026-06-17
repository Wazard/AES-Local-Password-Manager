"""Settings screen (autofill bridge, browser launch, anti-tamper)."""
import webbrowser
import customtkinter as ctk

from UI import icons
from UI.theme import (FONT_FAMILY, COLOR_BG_CARD, COLOR_SUCCESS, COLOR_MUTED,
                      COLOR_GOLD, COLOR_GOLD_HOVER, COLOR_CHARCOAL)
from UI.components import back_button, copy_button

ADDON_URL = "https://addons.mozilla.org/en-US/firefox/addon/securevault/"


class ExtensionMixin:
    def show_extension_screen(self):
        self.current_view = "extension"
        self.clear_screen()
        back_button(self)

        scroll = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4)

        ctk.CTkLabel(scroll, text=self.t("extension.title"),
                     font=(FONT_FAMILY, 22, "bold")).pack(pady=(0, 10))

        # Featured link to the published add-on.
        addon_icon = (icons.load_tinted("extension.png", 18, COLOR_CHARCOAL)
                      if icons.exists("extension.png") else None)
        ctk.CTkButton(scroll, text=self.t("extension.get_addon"), image=addon_icon,
                      fg_color=COLOR_GOLD, hover_color=COLOR_GOLD_HOVER,
                      text_color=COLOR_CHARCOAL, height=36,
                      command=lambda: webbrowser.open(ADDON_URL)).pack(pady=(0, 14))

        card = ctk.CTkFrame(scroll, fg_color=COLOR_BG_CARD, corner_radius=12)
        card.pack(fill="x", padx=26)

        # Enable toggle + status (this also enables browser-launch automatically)
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

        # Anti-tamper protection (opt-in).
        security_card = ctk.CTkFrame(scroll, fg_color=COLOR_BG_CARD, corner_radius=12)
        security_card.pack(fill="x", padx=26, pady=(14, 0))
        ctk.CTkCheckBox(security_card, text=self.t("extension.tamper"),
                        variable=self.tamper_enabled, command=self.toggle_tamper
                        ).pack(anchor="w", padx=16, pady=16)

        ctk.CTkLabel(scroll, text=self.t("extension.hint", port=self.ext_port),
                     font=(FONT_FAMILY, 11), text_color=COLOR_MUTED,
                     wraplength=420, justify="left").pack(padx=30, pady=(14, 0), anchor="w")
        ctk.CTkLabel(scroll, text=self.t("extension.tamper_hint"),
                     font=(FONT_FAMILY, 11), text_color=COLOR_MUTED,
                     wraplength=420, justify="left").pack(padx=30, pady=(4, 16), anchor="w")
