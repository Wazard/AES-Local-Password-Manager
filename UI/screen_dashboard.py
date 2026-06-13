"""Accounts dashboard: search, sort, and a grid/list view toggle."""
import customtkinter as ctk

from core import data_handler
from UI.theme import (FONT_FAMILY, COLOR_BG_CARD, COLOR_CARD_HOVER,
                      COLOR_SUCCESS, COLOR_SUCCESS_HOVER, COLOR_MUTED)

# View modes mapped to their toolbar glyphs (File-Explorer style).
VIEW_GLYPHS = {"▦": "grid", "☰": "list"}


class DashboardMixin:
    def show_dashboard(self):
        self.current_view = "dashboard"
        self.logged_in = True
        self.clear_screen()

        # --- Top toolbar: view toggle (left) + logout (right) ---
        topbar = ctk.CTkFrame(self.container, fg_color="transparent")
        topbar.pack(fill="x", padx=14, pady=(12, 0))

        glyph_for_mode = {mode: glyph for glyph, mode in VIEW_GLYPHS.items()}
        view_seg = ctk.CTkSegmentedButton(
            topbar, values=list(VIEW_GLYPHS.keys()), command=self._on_view_change,
            font=(FONT_FAMILY, 16), width=80)
        view_seg.set(glyph_for_mode[self.view_mode])
        view_seg.pack(side="left")

        ctk.CTkButton(topbar, text=self.t("dashboard.logout"), width=90, height=32,
                      fg_color=COLOR_BG_CARD, hover_color=COLOR_CARD_HOVER,
                      command=self.logout).pack(side="right")

        header = ctk.CTkFrame(self.container, height=60, fg_color="transparent")
        header.pack(fill="x", pady=(2, 6))
        ctk.CTkLabel(header, text=self.t("dashboard.title"),
                     font=(FONT_FAMILY, 24, "bold")).pack(expand=True)

        # --- Search + Sort controls ---
        controls = ctk.CTkFrame(self.container, fg_color="transparent")
        controls.pack(fill="x", padx=20, pady=(0, 6))

        self.search_entry = ctk.CTkEntry(
            controls, placeholder_text=self.t("dashboard.search"), height=36)
        self.search_entry.pack(side="left", fill="x", expand=True)
        if self.search_query:
            self.search_entry.insert(0, self.search_query)
        self.search_entry.bind("<KeyRelease>", self._on_search)

        # Map localized labels <-> internal sort modes so the menu localizes.
        self.sort_label_to_mode = {
            self.t("dashboard.sort_name_asc"): "name_asc",
            self.t("dashboard.sort_name_desc"): "name_desc",
            self.t("dashboard.sort_time_new"): "time_new",
            self.t("dashboard.sort_time_old"): "time_old",
        }
        mode_to_label = {v: k for k, v in self.sort_label_to_mode.items()}
        sort_menu = ctk.CTkOptionMenu(
            controls, values=list(self.sort_label_to_mode.keys()),
            command=self._on_sort_change, width=150, height=36)
        sort_menu.set(mode_to_label[self.sort_mode])
        sort_menu.pack(side="left", padx=(8, 0))

        # --- Account list ---
        self.dash_scroll = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        self.dash_scroll.pack(fill="both", expand=True, padx=20, pady=10)
        self._render_accounts()

        footer = ctk.CTkFrame(self.container, fg_color="transparent")
        footer.pack(fill="x", side="bottom", pady=20, padx=20)
        ctk.CTkButton(footer, text=self.t("dashboard.add_btn"), fg_color=COLOR_SUCCESS,
                      hover_color=COLOR_SUCCESS_HOVER, command=self.show_add_screen).pack(
                          side="left", expand=True, padx=5)
        ctk.CTkButton(footer, text=self.t("dashboard.gen_pass"),
                      command=self.show_gen_pass_screen).pack(side="left", expand=True, padx=5)

    def _on_search(self, _event=None):
        self.search_query = self.search_entry.get()
        self._render_accounts()

    def _on_sort_change(self, label):
        self.sort_mode = self.sort_label_to_mode.get(label, "name_asc")
        self._render_accounts()

    def _on_view_change(self, glyph):
        self.view_mode = VIEW_GLYPHS.get(glyph, "grid")
        self._render_accounts()

    def _render_accounts(self):
        """(Re)draws the filtered + sorted accounts in the current view mode."""
        for widget in self.dash_scroll.winfo_children():
            widget.destroy()

        if not self.vault_data:
            ctk.CTkLabel(self.dash_scroll, text=self.t("dashboard.no_accounts"),
                         font=(FONT_FAMILY, 16), text_color=COLOR_MUTED).pack(pady=60)
            ctk.CTkButton(self.dash_scroll, text=self.t("dashboard.add_btn").upper(),
                          fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER,
                          command=self.show_add_screen).pack()
            return

        services = data_handler.visible_services(
            self.vault_data, self.search_query, self.sort_mode)
        if not services:
            ctk.CTkLabel(self.dash_scroll, text=self.t("dashboard.no_results"),
                         font=(FONT_FAMILY, 16), text_color=COLOR_MUTED).pack(pady=60)
            return

        if self.view_mode == "list":
            self._render_list(services)
        else:
            self._render_grid(services)

    def _render_grid(self, services):
        self.dash_scroll.grid_columnconfigure((0, 1), weight=1)
        for i, service in enumerate(services):
            ctk.CTkButton(
                self.dash_scroll, text=service, height=80, corner_radius=12,
                font=(FONT_FAMILY, 15, "bold"),
                fg_color=COLOR_BG_CARD, hover_color=COLOR_CARD_HOVER,
                command=lambda s=service: self.show_details(s)
            ).grid(row=i // 2, column=i % 2, padx=8, pady=8, sticky="ew")

    def _render_list(self, services):
        for service in services:
            ctk.CTkButton(
                self.dash_scroll, text=service, anchor="w", height=44, corner_radius=10,
                font=(FONT_FAMILY, 14),
                fg_color=COLOR_BG_CARD, hover_color=COLOR_CARD_HOVER,
                command=lambda s=service: self.show_details(s)
            ).pack(fill="x", pady=5)
