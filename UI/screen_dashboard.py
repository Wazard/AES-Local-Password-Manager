"""Accounts dashboard: search, sort, and a grid/list view toggle."""
import customtkinter as ctk

from core import data_handler
from UI import icons
from UI.theme import (FONT_FAMILY, COLOR_BG_CARD, COLOR_CARD_HOVER, COLOR_STEEL,
                      COLOR_SUCCESS, COLOR_SUCCESS_HOVER, COLOR_MUTED, COLOR_GOLD,
                      COLOR_DANGER, COLOR_DANGER_HOVER)


class DashboardMixin:
    def show_dashboard(self):
        self.current_view = "dashboard"
        self.logged_in = True
        self.start_security_timers()
        self.clear_screen()

        # --- Top toolbar: view toggle (left) + logout (right) ---
        topbar = ctk.CTkFrame(self.container, fg_color="transparent")
        topbar.pack(fill="x", padx=14, pady=(12, 0))

        # View toggle: two icon buttons; the active mode is highlighted.
        self._view_grid_btn = ctk.CTkButton(
            topbar, text="", image=icons.load("show-large.png", 20), width=40, height=32,
            fg_color=COLOR_STEEL if self.view_mode == "grid" else COLOR_BG_CARD,
            hover_color=COLOR_CARD_HOVER, command=lambda: self._on_view_change("grid"))
        self._view_grid_btn.pack(side="left", padx=(0, 6))
        self._view_list_btn = ctk.CTkButton(
            topbar, text="", image=icons.load("show-inline.png", 20), width=40, height=32,
            fg_color=COLOR_STEEL if self.view_mode == "list" else COLOR_BG_CARD,
            hover_color=COLOR_CARD_HOVER, command=lambda: self._on_view_change("list"))
        self._view_list_btn.pack(side="left")

        lang_menu = ctk.CTkOptionMenu(
            topbar, values=self.lang_manager.get_supported_languages(),
            command=self.change_language, width=72, height=32)
        lang_menu.set(self.current_lang)
        lang_menu.pack(side="right")
        ctk.CTkButton(topbar, text="", image=icons.load("settings.png", 20), width=36, height=32,
                      fg_color=COLOR_BG_CARD, hover_color=COLOR_CARD_HOVER,
                      command=self.show_extension_screen).pack(side="right", padx=(0, 8))
        ctk.CTkButton(topbar, text="", image=icons.load("file-backup.png", 20), width=36, height=32,
                      fg_color=COLOR_BG_CARD, hover_color=COLOR_CARD_HOVER,
                      command=self.show_backup_screen).pack(side="right", padx=(0, 8))
        ctk.CTkButton(topbar, text="", image=icons.load("passkey.png", 20), width=36, height=32,
                      fg_color=COLOR_BG_CARD, hover_color=COLOR_CARD_HOVER,
                      command=self.show_change_master_screen).pack(side="right", padx=(0, 8))

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
        ctk.CTkButton(footer, text=self.t("dashboard.logout"), width=90,
                      fg_color=COLOR_DANGER, hover_color=COLOR_DANGER_HOVER,
                      command=self.logout).pack(side="right", padx=(5, 0))
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

    def _on_view_change(self, mode):
        self.view_mode = mode if mode in ("grid", "list") else "grid"
        self._view_grid_btn.configure(
            fg_color=COLOR_STEEL if self.view_mode == "grid" else COLOR_BG_CARD)
        self._view_list_btn.configure(
            fg_color=COLOR_STEEL if self.view_mode == "list" else COLOR_BG_CARD)
        self._render_accounts()

    def toggle_favourite(self, service):
        entry = self.vault_data.get(service)
        if entry is None:
            return
        entry["favourite"] = not entry.get("favourite", False)
        self.save_vault()
        self._render_accounts()

    def _star_button(self, parent, service, size):
        """A star toggle: star-fill.png (used as-is) when favourited, faded
        outline otherwise. Falls back to a gold-tinted star.png if no fill icon."""
        fav = self.vault_data[service].get("favourite", False)
        px = 20 if size >= 40 else 16
        if fav:
            img = (icons.load("star-fill.png", px) if icons.exists("star-fill.png")
                   else icons.load_tinted("star.png", px, COLOR_GOLD))
        else:
            img = icons.load_dimmed("star.png", px)
        return ctk.CTkButton(
            parent, text="", image=img, width=size, height=size, corner_radius=10,
            fg_color="transparent", hover_color=COLOR_CARD_HOVER,
            command=lambda s=service: self.toggle_favourite(s))

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
            card = ctk.CTkFrame(self.dash_scroll, fg_color=COLOR_BG_CARD,
                                corner_radius=12, height=92)
            card.grid(row=i // 2, column=i % 2, padx=8, pady=8, sticky="ew")
            card.grid_propagate(False)

            # Left-aligned name + username, vertically centered.
            text = ctk.CTkFrame(card, fg_color="transparent")
            text.place(relx=0.0, rely=0.5, x=16, anchor="w")
            name_lbl = ctk.CTkLabel(text, text=service, font=(FONT_FAMILY, 15, "bold"),
                                    anchor="w", justify="left")
            name_lbl.pack(anchor="w")
            clickable = [card, text, name_lbl]

            username = str(self.vault_data[service].get("user", ""))
            if username:
                user_lbl = ctk.CTkLabel(text, text=username, font=(FONT_FAMILY, 12),
                                        text_color=COLOR_MUTED, anchor="w", justify="left")
                user_lbl.pack(anchor="w")
                clickable.append(user_lbl)

            self._make_card_clickable(card, clickable, service)
            # Star in the top-right corner.
            self._star_button(card, service, size=28).place(relx=1.0, y=6, x=-6, anchor="ne")

    def _make_card_clickable(self, card, widgets, service):
        """Open details on click and highlight the card on hover, across all
        of its child widgets (so the whole block behaves as one button)."""
        def on_click(_e=None, s=service):
            self.show_details(s)

        def on_enter(_e=None):
            card.configure(fg_color=COLOR_CARD_HOVER)

        def on_leave(_e=None):
            card.configure(fg_color=COLOR_BG_CARD)

        for w in widgets:
            w.bind("<Button-1>", on_click)
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

    def _render_list(self, services):
        for service in services:
            card = ctk.CTkFrame(self.dash_scroll, fg_color=COLOR_BG_CARD,
                                corner_radius=10, height=44)
            card.pack(fill="x", pady=4)
            card.pack_propagate(False)
            # Star and name sit inside the same block.
            self._star_button(card, service, size=44).pack(side="left")
            ctk.CTkButton(
                card, text=service, anchor="w", height=44, corner_radius=10,
                font=(FONT_FAMILY, 14),
                fg_color="transparent", hover_color=COLOR_CARD_HOVER,
                command=lambda s=service: self.show_details(s)
            ).pack(side="left", fill="both", expand=True)
