"""Accounts dashboard: search, sort, favourites and a grid/list toggle.

Drawing account cards is by far the most expensive thing the app does, so the
dashboard is built once per session and kept (hidden while another screen is
up), and each card is kept too: a search or a re-sort only shows, hides and
re-orders the cards that already exist, and a new card is drawn only for an
account that doesn't have one yet or whose text changed.
"""
import customtkinter as ctk

from UI import components as ui
from UI import icons
from UI import theme as T

SEARCH_DEBOUNCE_MS = 120  # settle time after the last keystroke before redrawing


class _Card:
    """One drawn account card, kept between renders."""
    __slots__ = ("frame", "star", "mode", "subtitle", "favourite", "pos")

    def __init__(self, frame, star, mode, subtitle, favourite):
        self.frame = frame
        self.star = star
        self.mode = mode
        self.subtitle = subtitle
        self.favourite = favourite
        self.pos = None  # (row, column) while shown in the grid view

    def hide(self):
        if self.mode == "list":
            self.frame.pack_forget()
        else:
            self.frame.grid_forget()
            self.pos = None


class DashboardMixin:
    def show_dashboard(self):
        self.current_view = "dashboard"
        self.logged_in = True
        self.start_security_timers()
        ui.app_bar(self, left_builder=self._view_toggles, show_nav=True)

        if self._dash_screen is not None and self._dash_screen.winfo_exists():
            self._hide_screens()  # uncovers the dashboard, which never went away
            self._dash_screen.lift()
            self.screen = self._dash_screen
            self.search_entry.configure(takefocus="")
            self._set_hover(None)  # the pointer left whatever card it was on
        else:
            self._build_dashboard()
        self._render_accounts()

    def _on_dashboard_covered(self):
        """Another screen now sits on top of the dashboard. It is still there
        underneath, so keep the keyboard out of it: no Tab into the hidden
        search box, and no keystrokes or wheel events landing in it."""
        try:
            focused = self.focus_get()
        except Exception:  # Tk can't name some transient focus owners
            focused = None
        if focused is not None and str(focused).startswith(str(self._dash_screen) + "."):
            self.focus_set()
        self.search_entry.configure(takefocus=0)

    def _drop_dashboard(self):
        """Throw the kept dashboard away (logout, language change)."""
        screen = getattr(self, "_dash_screen", None)
        self._dash_screen = None
        self._cards = {}
        self._shown = []
        self._hover_card = None
        if screen is not None:
            try:
                screen.destroy()
            except Exception:
                pass

    def _build_dashboard(self):
        screen = self.clear_screen()
        self._dash_screen = screen
        self._search_after = None
        self._rendered = None  # nothing drawn yet: the first render can't be skipped
        self._cards = {}       # (view mode, service) -> _Card
        self._shown = []       # the cards on screen, in order
        self._empty = None
        self._hover_card = None
        self._paint_view_toggles()

        header = ctk.CTkFrame(screen, fg_color="transparent")
        header.pack(fill="x", padx=T.PAD_SCREEN, pady=(T.GAP_L, 0))
        ui.title(header, self.t("dashboard.title")).pack()
        self.count_label = ctk.CTkLabel(header, text="", font=T.font(T.S_SMALL),
                                        text_color=T.TEXT_MUTED)
        self.count_label.pack(pady=(2, 0))

        controls = ctk.CTkFrame(screen, fg_color="transparent")
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

        self.dash_scroll = ctk.CTkScrollableFrame(screen, fg_color="transparent")
        self.dash_scroll.pack(fill="both", expand=True,
                              padx=T.PAD_SCREEN - 8, pady=(T.GAP, 0))
        self.dash_scroll.grid_columnconfigure((0, 1), weight=1, uniform="col")

        bar = ui.footer(self)
        ui.primary_button(bar, self.t("dashboard.add_btn"),
                          self.show_add_screen, width=132).pack(side="left")
        ui.secondary_button(bar, self.t("dashboard.gen_pass"),
                            self.show_gen_pass_screen, width=164).pack(
                                side="left", padx=(T.GAP_S, 0))
        ui.danger_button(bar, self.t("dashboard.logout"), self.logout,
                         width=92).pack(side="right")

    def _view_toggles(self, parent):
        self._view_list_btn = ui.icon_button(
            parent, "show-inline.png", lambda: self._on_view_change("list"),
            active=self.view_mode == "list")
        self._view_list_btn.pack(side="left", padx=(T.GAP_S, 2))
        self._view_grid_btn = ui.icon_button(
            parent, "show-large.png", lambda: self._on_view_change("grid"),
            active=self.view_mode == "grid")
        self._view_grid_btn.pack(side="left")
        self._toggles_mode = self.view_mode

    def _paint_view_toggles(self):
        """The toggles live in the kept app bar, so they can outlive the view
        mode they were drawn for (a logout resets it)."""
        if getattr(self, "_toggles_mode", None) in (None, self.view_mode):
            return
        self._toggles_mode = self.view_mode
        for btn, name, mode_name in (
                (self._view_grid_btn, "show-large.png", "grid"),
                (self._view_list_btn, "show-inline.png", "list")):
            active = self.view_mode == mode_name
            btn.configure(
                fg_color=T.PRIMARY if active else "transparent",
                hover_color=T.PRIMARY_HOVER if active else T.CARD_HOVER,
                image=icons.load_tinted(
                    name, 18, T.ON_PRIMARY if active else T.TEXT_SECONDARY))

    def _on_search(self, _event=None):
        """Redraw shortly after the last keystroke rather than on each one:
        mid-word results are thrown away as fast as they are drawn."""
        self.search_query = self.search_entry.get()
        if self._search_after is not None:
            self.after_cancel(self._search_after)
        self._search_after = self.after(SEARCH_DEBOUNCE_MS, self._apply_search)

    def _apply_search(self):
        self._search_after = None
        if self.current_view == "dashboard":  # the screen may have changed since
            self._render_accounts()

    def _on_sort_change(self, label):
        self.sort_mode = self.sort_label_to_mode.get(label, "name_asc")
        self._render_accounts()

    def _on_view_change(self, mode):
        self.view_mode = mode if mode in ("grid", "list") else "list"
        self._paint_view_toggles()
        self._render_accounts()

    def toggle_favourite(self, service):
        entry = self.vault_data.get(service)
        if entry is None:
            return
        entry["favourite"] = not entry.get("favourite", False)
        self.save_vault()
        self._render_accounts()  # re-orders the cards and repaints this star only

    def _star_image(self, favourite):
        if favourite:
            return (icons.load("star-fill.png", 17) if icons.exists("star-fill.png")
                    else icons.load_tinted("star.png", 17, T.ACCENT))
        return icons.load_tinted("star.png", 17, T.TEXT_MUTED)

    def _star_button(self, parent, service, size=34):
        btn = ctk.CTkButton(
            parent, text="", width=size, height=size,
            image=self._star_image(self.vault_data[service].get("favourite", False)),
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
        """Shows the filtered + sorted accounts in the current view mode."""
        services = (self.search_cache.services(
            self.vault_data, self.vault_revision, self.search_query, self.sort_mode)
            if self.vault_data else [])

        total = len(self.vault_data)
        if self.count_label.winfo_exists():
            self.count_label.configure(
                text="" if not total else
                (self.t("dashboard.count_one") if total == 1
                 else self.t("dashboard.count", n=total)))

        # Typing "gith", "githu", "github" usually lands on the same accounts.
        state = (self.vault_revision, self.view_mode, tuple(services))
        if state == self._rendered:
            return
        self._rendered = state

        # Cards of accounts that are gone (deleted, renamed) go for good.
        gone = [self._cards.pop(k) for k in list(self._cards)
                if k[1] not in self.vault_data]
        for card in gone:
            if self._hover_card is card.frame:
                self._hover_card = None
            card.frame.destroy()
        if gone:
            self._shown = [c for c in self._shown if c not in gone]

        if not services:
            self._show_cards([])
            self._empty_state(self.t("dashboard.no_accounts") if not self.vault_data
                              else self.t("dashboard.no_results"))
            return

        wanted = [self._card_for(service) for service in services]
        self._show_cards(wanted)

    def _card_for(self, service):
        """The card for `service` in the current view mode — the kept one when
        its text still matches, otherwise a freshly drawn one."""
        mode = self.view_mode
        key = (mode, service)
        entry = self.vault_data[service]
        subtitle = self._entry_subtitle(service)
        card = self._cards.get(key)
        if card is not None and card.subtitle != subtitle:
            if card in self._shown:
                self._shown.remove(card)
            if self._hover_card is card.frame:
                self._hover_card = None
            card.frame.destroy()
            card = None
        if card is None:
            build = self._build_list_card if mode == "list" else self._build_grid_card
            card = build(service, subtitle)
            self._cards[key] = card
        favourite = bool(entry.get("favourite", False))
        if card.favourite != favourite:
            card.star.configure(image=self._star_image(favourite))
            card.favourite = favourite
        return card

    def _show_cards(self, wanted):
        """Lay out exactly `wanted`, in order. Cards that drop out are hidden,
        not destroyed, so clearing a search doesn't redraw them.

        Only cards that are out of place get touched: re-showing a hidden card
        is what costs (Windows re-shows each of its widgets), while moving one
        that is already showing is cheap — so a starred account jumping to the
        top moves that one card, not the whole list."""
        if self._empty is not None and wanted:
            self._empty.pack_forget()
        if wanted == self._shown:
            return
        keep = set(wanted)
        for card in self._shown:
            if card not in keep:
                card.hide()

        if wanted and wanted[0].mode == "grid":
            for i, card in enumerate(wanted):
                pos = (i // 2, i % 2)
                if card.pos != pos:
                    card.frame.grid(row=pos[0], column=pos[1], padx=4, pady=4,
                                    sticky="ew")
                    card.pos = pos
        else:
            order = [c for c in self._shown if c in keep]  # pack order right now
            for i, card in enumerate(wanted):
                if i < len(order) and order[i] is card:
                    continue
                if card in order:
                    order.remove(card)
                opts = {"fill": "x", "pady": 4, "padx": 2}
                if i < len(order):
                    opts["before"] = order[i].frame
                elif order:
                    opts["after"] = order[-1].frame
                card.frame.pack(**opts)
                order.insert(i, card)
        self._shown = list(wanted)

    def _empty_state(self, message):
        if self._empty is None:
            self._empty = ctk.CTkLabel(self.dash_scroll, text="", font=T.font(T.S_BODY),
                                       text_color=T.TEXT_MUTED)
        self._empty.configure(text=message)
        self._empty.pack(expand=True, pady=80)

    # --- Hover ---------------------------------------------------------------
    def _set_hover(self, card):
        """Highlight one card (or none). Recolouring a card redraws everything
        on it, so it only happens when the highlighted card actually changes."""
        old = self._hover_card
        if old is card:
            return
        self._hover_card = card
        if old is not None and old.winfo_exists():
            old.configure(fg_color=T.CARD)
        if card is not None:
            card.configure(fg_color=T.CARD_HOVER)

    def _hoverable(self, card, clickable, others, service):
        """Makes a whole card behave as one button. `clickable` open the
        account; `others` (the card's own buttons) only take part in hover."""
        def on_click(_e=None, s=service):
            self.show_details(s)

        def on_enter(_e=None):
            self._set_hover(card)

        def on_leave(event):
            # Moving between a card's own parts fires Leave on one and Enter
            # on the next; only a pointer that has left the card counts.
            if self._hover_card is not card:
                return
            try:
                under = card.winfo_containing(event.x_root, event.y_root)
            except Exception:  # pointer over another app's window
                under = None
            if under is not None and (under is card or
                                      str(under).startswith(str(card) + ".")):
                return
            self._set_hover(None)

        for w in clickable:
            w.bind("<Button-1>", on_click, add="+")
        for w in clickable + others:
            w.bind("<Enter>", on_enter, add="+")
            w.bind("<Leave>", on_leave, add="+")

    def _entry_subtitle(self, service):
        entry = self.vault_data[service]
        return str(entry.get("user") or entry.get("url") or "")

    # --- Cards -----------------------------------------------------------------
    # Each CustomTkinter widget is a canvas of its own, which is what makes
    # cards expensive, so they are laid out directly on the card: no wrapper
    # frame and no spacer frames for centring.
    def _build_list_card(self, service, subtitle):
        card = ui.card(self.dash_scroll, height=56)
        card.grid_propagate(False)
        card.grid_columnconfigure(1, weight=1)
        card.grid_rowconfigure((0, 1), weight=1)

        star = self._star_button(card, service)
        star.grid(row=0, column=0, rowspan=2, padx=(8, 0))
        copy = self._copy_pw_button(card, service)
        copy.grid(row=0, column=2, rowspan=2, padx=(0, 10))

        name = ctk.CTkLabel(card, text=service, font=T.font(T.S_BODY, "bold"),
                            text_color=T.TEXT, anchor="w", height=22)
        clickable = [card, name]
        if subtitle:
            name.grid(row=0, column=1, sticky="sew", padx=(8, 0))
            sub = ctk.CTkLabel(card, text=subtitle, font=T.font(T.S_SMALL),
                               text_color=T.TEXT_MUTED, anchor="w", height=18)
            sub.grid(row=1, column=1, sticky="new", padx=(8, 0))
            clickable.append(sub)
        else:
            name.grid(row=0, column=1, rowspan=2, sticky="ew", padx=(8, 0))
        self._hoverable(card, clickable, [star, copy], service)
        return _Card(card, star, "list", subtitle,
                     bool(self.vault_data[service].get("favourite", False)))

    def _build_grid_card(self, service, subtitle):
        card = ui.card(self.dash_scroll, height=T.H_CARD + 14)
        card.grid_propagate(False)

        name = ctk.CTkLabel(card, text=service, font=T.font(T.S_BODY, "bold"),
                            text_color=T.TEXT, anchor="w", justify="left")
        clickable = [card, name]
        if subtitle:
            name.place(relx=0.0, rely=0.5, x=14, anchor="sw")
            sub = ctk.CTkLabel(card, text=subtitle, font=T.font(T.S_SMALL),
                               text_color=T.TEXT_MUTED, anchor="w", justify="left")
            sub.place(relx=0.0, rely=0.5, x=14, anchor="nw")
            clickable.append(sub)
        else:
            name.place(relx=0.0, rely=0.5, x=14, anchor="w")

        star = self._star_button(card, service, size=28)
        star.place(relx=1.0, y=6, x=-6, anchor="ne")
        copy = self._copy_pw_button(card, service)
        copy.place(relx=1.0, rely=1.0, x=-8, y=-6, anchor="se")
        self._hoverable(card, clickable, [star, copy], service)
        return _Card(card, star, "grid", subtitle,
                     bool(self.vault_data[service].get("favourite", False)))
