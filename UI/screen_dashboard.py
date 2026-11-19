"""Accounts dashboard: search, sort, favourites and a grid/list toggle."""
import customtkinter as ctk

from core import data_handler
from UI import components as ui
from UI import icons
from UI import theme as T


class DashboardMixin:
    def show_dashboard(self):
        self.current_view = "dashboard"
        self.logged_in = True
        self.start_security_timers()
        self.clear_screen()

        ui.app_bar(self, left_builder=self._view_toggles, show_nav=True)

        header = ctk.CTkFrame(self.container, fg_color="transparent")
        header.pack(fill="x", padx=T.PAD_SCREEN, pady=(T.GAP_L, 0))
        ui.title(header, self.t("dashboard.title")).pack()
        self.count_label = ctk.CTkLabel(header, text="", font=T.font(T.S_SMALL),
                                        text_color=T.TEXT_MUTED)
        self.count_label.pack(pady=(2, 0))

        controls = ctk.CTkFrame(self.container, fg_color="transparent")
        controls.pack(fill="x", padx=T.PAD_SCREEN, pady=(T.GAP, 0))

        self.search_entry = ui.text_field(
            controls, placeholder=self.t("dashboard.search"),
            value=self.search_query)
        self.search_entry.pack(side="left", fill="x", expand=True)
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
            command=self._on_sort_change, width=148, height=T.H_INPUT,
            font=T.font(T.S_LABEL), dropdown_font=T.font(T.S_LABEL),
            fg_color=T.SECONDARY, button_color=T.SECONDARY,
            button_hover_color=T.SECONDARY_HOVER)
        sort_menu.set(mode_to_label[self.sort_mode])
        sort_menu.pack(side="left", padx=(T.GAP_S, 0))

        self.dash_scroll = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        self.dash_scroll.pack(fill="both", expand=True,
                              padx=T.PAD_SCREEN - 8, pady=(T.GAP, 0))

        bar = ui.footer(self)
        ui.primary_button(bar, self.t("dashboard.add_btn"),
                          self.show_add_screen, width=132).pack(side="left")
        ui.secondary_button(bar, self.t("dashboard.gen_pass"),
                            self.show_gen_pass_screen, width=164).pack(
                                side="left", padx=(T.GAP_S, 0))
        ui.danger_button(bar, self.t("dashboard.logout"), self.logout,
                         width=92).pack(side="right")

        self._render_accounts()

    def _view_toggles(self, parent):
        self._view_list_btn = ui.icon_button(
            parent, "show-inline.png", lambda: self._on_view_change("list"),
            active=self.view_mode == "list")
        self._view_list_btn.pack(side="left", padx=(T.GAP_S, 2))
        self._view_grid_btn = ui.icon_button(
            parent, "show-large.png", lambda: self._on_view_change("grid"),
            active=self.view_mode == "grid")
        self._view_grid_btn.pack(side="left")

    def _on_search(self, _event=None):
        self.search_query = self.search_entry.get()
        self._render_accounts()

    def _on_sort_change(self, label):
        self.sort_mode = self.sort_label_to_mode.get(label, "name_asc")
        self._render_accounts()

    def _on_view_change(self, mode):
        self.view_mode = mode if mode in ("grid", "list") else "list"
        for btn, name, mode_name in (
                (self._view_grid_btn, "show-large.png", "grid"),
                (self._view_list_btn, "show-inline.png", "list")):
            active = self.view_mode == mode_name
            btn.configure(
                fg_color=T.PRIMARY if active else "transparent",
                hover_color=T.PRIMARY_HOVER if active else T.CARD_HOVER,
                image=icons.load_tinted(
                    name, 18, T.ON_PRIMARY if active else T.TEXT_SECONDARY))
        self._render_accounts()

    def toggle_favourite(self, service):
        entry = self.vault_data.get(service)
        if entry is None:
            return
        entry["favourite"] = not entry.get("favourite", False)
        self.save_vault()
        self._render_accounts()

    def _star_button(self, parent, service, size=34):
        fav = self.vault_data[service].get("favourite", False)
        if fav:
            img = (icons.load("star-fill.png", 17) if icons.exists("star-fill.png")
                   else icons.load_tinted("star.png", 17, T.ACCENT))
        else:
            img = icons.load_tinted("star.png", 17, T.TEXT_MUTED)
        btn = ctk.CTkButton(
            parent, text="", image=img, width=size, height=size,
            corner_radius=T.R_BTN, fg_color="transparent",
            hover_color=T.CARD_HOVER,
            command=lambda s=service: self.toggle_favourite(s))
        ui.attach_tooltip(btn, self.t("dashboard.favourite"))
        return btn

    def _copy_pw_button(self, parent, service):
        btn = ctk.CTkButton(
            parent, text="", image=icons.load_tinted("copy.png", 16, T.TEXT_MUTED),
            width=32, height=32, corner_radius=T.R_BTN, fg_color="transparent",
            hover_color=T.CARD_HOVER)

        def do_copy():
            self.copy_to_clipboard(self.get_password(service))
            btn.configure(image=icons.load_tinted("copy.png", 16, T.POSITIVE))
            btn.after(1200, lambda: btn.winfo_exists() and btn.configure(
                image=icons.load_tinted("copy.png", 16, T.TEXT_MUTED)))

        btn.configure(command=do_copy)
        ui.attach_tooltip(btn, self.t("dashboard.copy_password"))
        return btn

    def _render_accounts(self):
        """(Re)draws the filtered + sorted accounts in the current view mode."""
        for widget in self.dash_scroll.winfo_children():
            widget.destroy()

        total = len(self.vault_data)
        if self.count_label.winfo_exists():
            self.count_label.configure(
                text="" if not total else
                (self.t("dashboard.count_one") if total == 1
                 else self.t("dashboard.count", n=total)))

        if not self.vault_data:
            self._empty_state(self.t("dashboard.no_accounts"))
            return

        services = data_handler.visible_services(
            self.vault_data, self.search_query, self.sort_mode)
        if not services:
            self._empty_state(self.t("dashboard.no_results"))
            return

        if self.view_mode == "list":
            self._render_list(services)
        else:
            self._render_grid(services)

    def _empty_state(self, message):
        box = ctk.CTkFrame(self.dash_scroll, fg_color="transparent")
        box.pack(expand=True, pady=80)
        ctk.CTkLabel(box, text=message, font=T.font(T.S_BODY),
                     text_color=T.TEXT_MUTED).pack()

    def _hoverable(self, card, widgets, service):
        """Makes a whole card behave as one button."""
        def on_click(_e=None, s=service):
            self.show_details(s)

        def on_enter(_e=None):
            if card.winfo_exists():
                card.configure(fg_color=T.CARD_HOVER)

        def on_leave(_e=None):
            if card.winfo_exists():
                card.configure(fg_color=T.CARD)

        for w in widgets:
            w.bind("<Button-1>", on_click)
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

    def _entry_subtitle(self, service):
        entry = self.vault_data[service]
        return str(entry.get("user") or entry.get("url") or "")

    def _render_list(self, services):
        for service in services:
            card = ui.card(self.dash_scroll, height=56)
            card.pack(fill="x", pady=4, padx=2)
            card.pack_propagate(False)

            self._star_button(card, service).pack(side="left", padx=(8, 0))
            self._copy_pw_button(card, service).pack(side="right", padx=(0, 10))

            text = ctk.CTkFrame(card, fg_color="transparent")
            text.pack(side="left", fill="both", expand=True, padx=(8, 0))
            spacer_top = ctk.CTkFrame(text, fg_color="transparent", width=1, height=0)
            spacer_top.pack(expand=True)
            name = ctk.CTkLabel(text, text=service, font=T.font(T.S_BODY, "bold"),
                                text_color=T.TEXT, anchor="w")
            name.pack(anchor="w")
            widgets = [card, text, name, spacer_top]
            subtitle = self._entry_subtitle(service)
            if subtitle:
                sub = ctk.CTkLabel(text, text=subtitle, font=T.font(T.S_SMALL),
                                   text_color=T.TEXT_MUTED, anchor="w")
                sub.pack(anchor="w")
                widgets.append(sub)
            spacer_bottom = ctk.CTkFrame(text, fg_color="transparent", width=1, height=0)
            spacer_bottom.pack(expand=True)
            widgets.append(spacer_bottom)
            self._hoverable(card, widgets, service)

    def _render_grid(self, services):
        self.dash_scroll.grid_columnconfigure((0, 1), weight=1, uniform="col")
        for i, service in enumerate(services):
            card = ui.card(self.dash_scroll, height=T.H_CARD + 14)
            card.grid(row=i // 2, column=i % 2, padx=4, pady=4, sticky="ew")
            card.grid_propagate(False)

            text = ctk.CTkFrame(card, fg_color="transparent")
            text.place(relx=0.0, rely=0.5, x=14, anchor="w")
            name = ctk.CTkLabel(text, text=service, font=T.font(T.S_BODY, "bold"),
                                text_color=T.TEXT, anchor="w", justify="left")
            name.pack(anchor="w")
            widgets = [card, text, name]
            subtitle = self._entry_subtitle(service)
            if subtitle:
                sub = ctk.CTkLabel(text, text=subtitle, font=T.font(T.S_SMALL),
                                   text_color=T.TEXT_MUTED, anchor="w", justify="left")
                sub.pack(anchor="w")
                widgets.append(sub)

            self._hoverable(card, widgets, service)
            self._star_button(card, service, size=28).place(relx=1.0, y=6, x=-6, anchor="ne")
            self._copy_pw_button(card, service).place(
                relx=1.0, rely=1.0, x=-8, y=-6, anchor="se")
