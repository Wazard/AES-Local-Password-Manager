import os
import json
import time
import secrets
import threading
import customtkinter as ctk
from tkinter import messagebox

# Optional system-tray support (Windows). Degrades gracefully if missing.
try:
    import pystray
    from PIL import Image
    _TRAY_AVAILABLE = True
except Exception:
    _TRAY_AVAILABLE = False

# Existing backend imports
from core import encryption
from core import storage_handler
from core import storage_compression
from core import data_handler
from core import password_generator
from localization.language_manager import LanguageManager

# --- Cozy, earthy palette (from the supplied swatches) ---
COLOR_CREAM = "#F4F6E4"   # pale cream  – text on dark
COLOR_OLIVE = "#899248"   # olive green – primary actions
COLOR_MAUVE = "#A9839C"   # dusty mauve – secondary actions
COLOR_TAUPE = "#8C7A68"   # warm taupe  – muted accents
COLOR_PLUM = "#4F2442"    # deep plum   – background

# Derived shades for surfaces / hovers
COLOR_BG = COLOR_PLUM
COLOR_BG_CARD = "#5E3354"
COLOR_CARD_HOVER = "#6E3F63"
COLOR_TEXT = COLOR_CREAM

COLOR_SUCCESS = COLOR_OLIVE
COLOR_SUCCESS_HOVER = "#76803C"
COLOR_DANGER = "#B5524A"
COLOR_DANGER_HOVER = "#9C443D"
COLOR_ACCENT = COLOR_MAUVE
COLOR_ACCENT_HOVER = "#967089"
COLOR_MUTED = "#C2AEBB"

FONT_FAMILY = "Segoe UI"

ANIMATION_DURATION = 1.2 # seconds


def _apply_cozy_theme():
    """Override CustomTkinter's default theme so every widget is cozy,
    and make scrollbars invisible (still scrollable via the mouse wheel)."""
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    tm = ctk.ThemeManager.theme

    def dual(c):
        return [c, c]

    tm["CTk"]["fg_color"] = dual(COLOR_BG)
    tm["CTkToplevel"]["fg_color"] = dual(COLOR_BG)
    tm["CTkFrame"]["fg_color"] = dual(COLOR_BG)
    tm["CTkFrame"]["top_fg_color"] = dual(COLOR_BG_CARD)
    tm["CTkFrame"]["border_color"] = dual(COLOR_BG_CARD)

    tm["CTkLabel"]["text_color"] = dual(COLOR_TEXT)

    tm["CTkButton"]["fg_color"] = dual(COLOR_ACCENT)
    tm["CTkButton"]["hover_color"] = dual(COLOR_ACCENT_HOVER)
    tm["CTkButton"]["text_color"] = dual(COLOR_TEXT)

    tm["CTkEntry"]["fg_color"] = dual(COLOR_BG_CARD)
    tm["CTkEntry"]["border_color"] = dual(COLOR_BG_CARD)
    tm["CTkEntry"]["text_color"] = dual(COLOR_TEXT)
    tm["CTkEntry"]["placeholder_text_color"] = dual(COLOR_MUTED)

    tm["CTkOptionMenu"]["fg_color"] = dual(COLOR_ACCENT)
    tm["CTkOptionMenu"]["button_color"] = dual(COLOR_ACCENT_HOVER)
    tm["CTkOptionMenu"]["button_hover_color"] = dual(COLOR_OLIVE)
    tm["CTkOptionMenu"]["text_color"] = dual(COLOR_TEXT)

    tm["DropdownMenu"]["fg_color"] = dual(COLOR_BG_CARD)
    tm["DropdownMenu"]["hover_color"] = dual(COLOR_ACCENT)
    tm["DropdownMenu"]["text_color"] = dual(COLOR_TEXT)

    tm["CTkCheckBox"]["fg_color"] = dual(COLOR_OLIVE)
    tm["CTkCheckBox"]["hover_color"] = dual(COLOR_SUCCESS_HOVER)
    tm["CTkCheckBox"]["text_color"] = dual(COLOR_TEXT)
    tm["CTkCheckBox"]["checkmark_color"] = dual(COLOR_CREAM)

    tm["CTkSlider"]["button_color"] = dual(COLOR_OLIVE)
    tm["CTkSlider"]["button_hover_color"] = dual(COLOR_SUCCESS_HOVER)
    tm["CTkSlider"]["progress_color"] = dual(COLOR_MAUVE)

    # Hide scrollbars: blend them into the background (still wheel-scrollable).
    tm["CTkScrollbar"]["fg_color"] = dual(COLOR_BG)
    tm["CTkScrollbar"]["button_color"] = dual(COLOR_BG)
    tm["CTkScrollbar"]["button_hover_color"] = dual(COLOR_BG)


_apply_cozy_theme()

class PasswordManagerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Localization State
        self.lang_manager = LanguageManager()
        self.current_lang = "en"
        self.current_view = "auth"
        self.active_service = None # For detail/modify tracking

        # Dashboard search/sort state
        self.search_query = ""
        self.sort_mode = "name_asc"
        self.logged_in = False

        # Generator animation state
        self._gen_token = 0
        self._gen_after = None

        self.title("Secure Vault")
        self.geometry("520x600")
        self.minsize(460, 520)

        # System-tray state
        self._icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
        self.minimize_to_tray = ctk.BooleanVar(value=False)
        self.tray_icon = None
        try:
            self.iconbitmap(self._icon_path)
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.master_password = ""
        self.vault_data = {}

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        self.show_auth_screen()

    # --- System tray / window lifecycle ---
    def _on_close(self):
        """Minimise to the Windows tray when the toggle is on; otherwise quit."""
        if self.minimize_to_tray.get() and _TRAY_AVAILABLE:
            self._hide_to_tray()
        else:
            self._quit_app()

    def _hide_to_tray(self):
        self.withdraw()
        if self.tray_icon is None:
            self._create_tray_icon()

    def _create_tray_icon(self):
        try:
            image = Image.open(self._icon_path)
        except Exception:
            image = Image.new("RGB", (64, 64), COLOR_PLUM)
        menu = pystray.Menu(
            pystray.MenuItem(self.t("tray.open"), self._tray_open, default=True),
            pystray.MenuItem(self.t("tray.quit"), self._tray_quit),
        )
        self.tray_icon = pystray.Icon("secure_vault", image, "Secure Vault", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _tray_open(self, icon=None, item=None):
        # Tray callbacks run off the main thread; bounce back to the Tk loop.
        self.after(0, self._restore_window)

    def _restore_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _tray_quit(self, icon=None, item=None):
        self.after(0, self._quit_app)

    def _quit_app(self):
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
        self.destroy()

    def logout(self):
        """Clear the decrypted session and return to the login screen."""
        self.master_password = ""
        self.vault_data = {}
        self.search_query = ""
        self.sort_mode = "name_asc"
        self.logged_in = False
        self.show_auth_screen()

    # --- Account ordering / filtering helpers ---
    def get_visible_services(self):
        """Returns service names filtered by the search query and sorted."""
        services = list(self.vault_data.keys())

        query = self.search_query.strip().lower()
        if query:
            services = [
                s for s in services
                if query in s.lower()
                or query in str(self.vault_data[s].get("user", "")).lower()
            ]

        if self.sort_mode == "name_asc":
            services.sort(key=str.lower)
        elif self.sort_mode == "name_desc":
            services.sort(key=str.lower, reverse=True)
        elif self.sort_mode == "time_new":
            services.sort(key=lambda s: self.vault_data[s].get("created", 0), reverse=True)
        elif self.sort_mode == "time_old":
            services.sort(key=lambda s: self.vault_data[s].get("created", 0))
        return services

    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)

    def _back_button(self, command=None):
        ctk.CTkButton(self.container, text="←", width=36, height=36,
                      fg_color=COLOR_BG_CARD, hover_color=COLOR_CARD_HOVER,
                      font=(FONT_FAMILY, 16, "bold"),
                      command=command or self.show_dashboard).pack(anchor="nw", padx=14, pady=14)

    def _copy_button(self, parent, get_text):
        """A small COPY button that flashes 'COPIED!' briefly when clicked."""
        btn = ctk.CTkButton(parent, text=self.t("generator.copy"), width=80, height=32)

        def do_copy():
            self.copy_to_clipboard(get_text())
            btn.configure(text=self.t("generator.copied"), fg_color=COLOR_SUCCESS)
            self.after(1200, lambda: btn.winfo_exists() and
                       btn.configure(text=self.t("generator.copy"), fg_color=COLOR_ACCENT))

        btn.configure(command=do_copy)
        return btn

    def t(self, key, **kwargs):
        """Translation helper function."""
        return self.lang_manager.get_text(key, self.current_lang, **kwargs)

    def change_language(self, new_lang):
        """Refresh the current screen with the new language."""
        self.current_lang = new_lang
        # Real-time UI refresh based on state
        view_map = {
            "auth": self.show_auth_screen,
            "dashboard": self.show_dashboard,
            "add": lambda: self.show_add_screen(),
            "modify": lambda: self.show_add_screen(self.active_service),
            "details": lambda: self.show_details(self.active_service),
            "list_all": self.show_list_all,
            "generator": self.show_gen_pass_screen
        }
        view_map[self.current_view]()

    def clear_screen(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def save_vault(self):
        try:
            json_data = json.dumps(self.vault_data)
            compressed = storage_compression.compress_data(json_data)
            encrypted = encryption.encrypt_data(compressed, self.master_password)
            storage_handler.write_vault(encrypted)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Save failed: {e}")
            return False

    # --- Screen 1: Authentication ---
    def show_auth_screen(self):
        self.current_view = "auth"
        self.logged_in = False
        self.clear_screen()
        
        # Dynamically fetch languages from the JSON file
        available_langs = self.lang_manager.get_supported_languages() 
        
        lang_menu = ctk.CTkOptionMenu(
            self.container, 
            values=available_langs, # No longer hardcoded
            command=self.change_language, 
            width=70
        )
        lang_menu.set(self.current_lang)
        lang_menu.place(relx=0.98, rely=0.02, anchor="ne")

        frame = ctk.CTkFrame(self.container, fg_color="transparent")
        frame.place(relx=0.5, rely=0.4, anchor="center")
        
        ctk.CTkLabel(frame, text=self.t("auth.title"), font=(FONT_FAMILY, 28, "bold")).pack(pady=20)
        self.pass_entry = ctk.CTkEntry(frame, placeholder_text=self.t("auth.placeholder"),
                                       show="*", width=260, height=40)
        self.pass_entry.pack(pady=10)
        self.pass_entry.bind("<Return>", lambda _e: self.attempt_login())

        self.status_label = ctk.CTkLabel(frame, text="")
        self.status_label.pack()
        ctk.CTkButton(frame, text=self.t("auth.login_btn"), height=40, width=260,
                      fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER,
                      command=self.attempt_login).pack(pady=(20, 8))

        # Generate a password without logging in.
        ctk.CTkButton(frame, text=self.t("auth.generate_btn"), height=40, width=260,
                      command=self.show_gen_pass_screen).pack(pady=(0, 16))

        # "Remind me" / keep running in the Windows tray on close.
        tray_chk = ctk.CTkCheckBox(frame, text=self.t("auth.tray"),
                                   variable=self.minimize_to_tray)
        tray_chk.pack(pady=(0, 4))
        if not _TRAY_AVAILABLE:
            tray_chk.configure(state="disabled")

    def attempt_login(self):
        pwd = self.pass_entry.get()
        raw_blob = storage_handler.read_vault()
        if not raw_blob:
            self.master_password = pwd
            self.vault_data = {}
            self.show_dashboard()
            return
        try:
            decrypted = encryption.decrypt_data(raw_blob, pwd)
            decompressed = storage_compression.decompress_data(decrypted)
            self.vault_data = json.loads(decompressed)
            self.master_password = pwd
            self.status_label.configure(text=self.t("auth.correct"), text_color=COLOR_SUCCESS)
            self.after(500, self.show_dashboard)
        except Exception:
            self.status_label.configure(text=self.t("auth.wrong"), text_color=COLOR_DANGER)

    # --- Screen 2 & 3: Dashboard ---
    def show_dashboard(self):
        self.current_view = "dashboard"
        self.logged_in = True
        self.clear_screen()

        topbar = ctk.CTkFrame(self.container, fg_color="transparent")
        topbar.pack(fill="x", padx=14, pady=(12, 0))
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
        ctk.CTkButton(footer, text=self.t("dashboard.list_all"),
                      command=self.show_list_all).pack(side="left", expand=True, padx=5)
        ctk.CTkButton(footer, text=self.t("dashboard.gen_pass"),
                      command=self.show_gen_pass_screen).pack(side="left", expand=True, padx=5)

    def _on_search(self, _event=None):
        self.search_query = self.search_entry.get()
        self._render_accounts()

    def _on_sort_change(self, label):
        self.sort_mode = self.sort_label_to_mode.get(label, "name_asc")
        self._render_accounts()

    def _render_accounts(self):
        """(Re)draws the filtered + sorted account cards into the scroll frame."""
        for widget in self.dash_scroll.winfo_children():
            widget.destroy()

        if not self.vault_data:
            ctk.CTkLabel(self.dash_scroll, text=self.t("dashboard.no_accounts"),
                         font=(FONT_FAMILY, 16), text_color=COLOR_MUTED).pack(pady=60)
            ctk.CTkButton(self.dash_scroll, text=self.t("dashboard.add_btn").upper(),
                          fg_color=COLOR_SUCCESS, hover_color=COLOR_SUCCESS_HOVER,
                          command=self.show_add_screen).pack()
            return

        services = self.get_visible_services()
        if not services:
            ctk.CTkLabel(self.dash_scroll, text=self.t("dashboard.no_results"),
                         font=(FONT_FAMILY, 16), text_color=COLOR_MUTED).pack(pady=60)
            return

        self.dash_scroll.grid_columnconfigure((0, 1), weight=1)
        for i, service in enumerate(services):
            card = ctk.CTkButton(
                self.dash_scroll, text=service, height=80, corner_radius=12,
                font=(FONT_FAMILY, 15, "bold"),
                fg_color=COLOR_BG_CARD, hover_color=COLOR_CARD_HOVER,
                command=lambda s=service: self.show_details(s))
            card.grid(row=i // 2, column=i % 2, padx=8, pady=8, sticky="ew")

    # --- Screen 4: Add/Modify ---
    def show_add_screen(self, edit_service=None):
        self.active_service = edit_service
        self.current_view = "modify" if edit_service else "add"
        self.clear_screen()
        title = self.t("forms.new_title") if not edit_service else self.t("forms.modify_title", service=edit_service)
        
        self._back_button()
        ctk.CTkLabel(self.container, text=title, font=(FONT_FAMILY, 22, "bold")).pack(pady=10)

        form = ctk.CTkFrame(self.container, fg_color="transparent")
        form.pack(pady=20, padx=40, fill="x")

        ctk.CTkLabel(form, text=self.t("forms.account"), font=(FONT_FAMILY, 12, "bold")).pack(anchor="w")
        acc_entry = ctk.CTkEntry(form, height=38)
        acc_entry.pack(fill="x", pady=(2, 15))
        if edit_service: acc_entry.insert(0, edit_service); acc_entry.configure(state="disabled")

        ctk.CTkLabel(form, text=self.t("forms.username"), font=(FONT_FAMILY, 12, "bold")).pack(anchor="w")
        user_entry = ctk.CTkEntry(form, height=38)
        user_entry.pack(fill="x", pady=(2, 15))
        if edit_service: user_entry.insert(0, self.vault_data[edit_service]['user'])

        ctk.CTkLabel(form, text=self.t("forms.password"), font=(FONT_FAMILY, 12, "bold")).pack(anchor="w")
        pwd_frame = ctk.CTkFrame(form, fg_color="transparent")
        pwd_frame.pack(fill="x", pady=(2, 0))
        pwd_entry = ctk.CTkEntry(pwd_frame, height=38)
        pwd_entry.pack(side="left", fill="x", expand=True)
        if edit_service: pwd_entry.insert(0, self.vault_data[edit_service]['pass'])

        ctk.CTkButton(pwd_frame, text=self.t("forms.generate"), width=90, height=38,
                      command=lambda: [pwd_entry.delete(0, 'end'),
                                       pwd_entry.insert(0, password_generator.generate_secure_password())]
                      ).pack(side="right", padx=(8, 0))

        def save_action():
            service = acc_entry.get().strip()
            if not service: return
            existing = self.vault_data.get(service, {})
            self.vault_data[service] = {
                "user": user_entry.get(),
                "pass": pwd_entry.get(),
                "created": existing.get("created", time.time()),
            }
            if self.save_vault(): self.show_dashboard()

        ctk.CTkButton(self.container, text=self.t("forms.save"), fg_color=COLOR_SUCCESS,
                      hover_color=COLOR_SUCCESS_HOVER, height=40, width=200,
                      command=save_action).pack(pady=30)

    # --- Screen 5: Account Detail ---
    def show_details(self, service):
        self.active_service = service
        self.current_view = "details"
        self.clear_screen()
        self._back_button()
        ctk.CTkLabel(self.container, text=service, font=(FONT_FAMILY, 24, "bold")).pack(pady=20)

        detail_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        detail_frame.pack(padx=40, fill="x")

        # Username row
        ctk.CTkLabel(detail_frame, text=self.t("details.username_label"),
                     font=(FONT_FAMILY, 12, "bold")).pack(anchor="w")
        user_row = ctk.CTkFrame(detail_frame, fg_color="transparent")
        user_row.pack(fill="x", pady=(2, 18))
        user_disp = ctk.CTkEntry(user_row, fg_color=COLOR_BG_CARD, border_width=0, height=38)
        user_disp.insert(0, self.vault_data[service]['user'])
        user_disp.configure(state="readonly")
        user_disp.pack(side="left", fill="x", expand=True)
        self._copy_button(user_row, lambda: self.vault_data[service]['user']).pack(side="right", padx=(8, 0))

        # Password row
        ctk.CTkLabel(detail_frame, text=self.t("details.password_label"),
                     font=(FONT_FAMILY, 12, "bold")).pack(anchor="w")
        pass_row = ctk.CTkFrame(detail_frame, fg_color="transparent")
        pass_row.pack(fill="x", pady=(2, 0))
        pass_disp = ctk.CTkEntry(pass_row, fg_color=COLOR_BG_CARD, border_width=0, height=38,
                                 font=("Courier New", 14))
        pass_disp.insert(0, self.vault_data[service]['pass'])
        pass_disp.configure(state="readonly")
        pass_disp.pack(side="left", fill="x", expand=True)
        self._copy_button(pass_row, lambda: self.vault_data[service]['pass']).pack(side="right", padx=(8, 0))

        btn_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        btn_frame.pack(side="bottom", pady=40)
        ctk.CTkButton(btn_frame, text=self.t("details.modify"), fg_color=COLOR_SUCCESS,
                      hover_color=COLOR_SUCCESS_HOVER,
                      command=lambda: self.show_add_screen(service)).pack(side="left", padx=10)

        def delete_action():
            if messagebox.askyesno("Confirm", self.t("details.delete_confirm", service=service)):
                if data_handler.delete_entry(self.vault_data, service):
                    self.save_vault()
                    self.show_dashboard()
        ctk.CTkButton(btn_frame, text=self.t("details.delete"), fg_color=COLOR_DANGER,
                      hover_color=COLOR_DANGER_HOVER, command=delete_action).pack(side="left", padx=10)

    # --- Screen 6: All Accounts List ---
    def show_list_all(self):
        self.current_view = "list_all"
        self.clear_screen()
        self._back_button()
        ctk.CTkLabel(self.container, text=self.t("list_all.title"), font=(FONT_FAMILY, 22, "bold")).pack(pady=10)
        scroll = ctk.CTkScrollableFrame(self.container, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=10)
        for service in sorted(self.vault_data.keys(), key=str.lower):
            ctk.CTkButton(scroll, text=service, anchor="w", height=44, corner_radius=10,
                          font=(FONT_FAMILY, 14), fg_color=COLOR_BG_CARD, hover_color=COLOR_CARD_HOVER,
                          command=lambda s=service: self.show_details(s)).pack(fill="x", pady=5)

    # --- Screen 7: Animated Password Generator ---
    def show_gen_pass_screen(self):
        self.current_view = "generator"
        self.clear_screen()
        self._back_button(self.show_dashboard if self.logged_in else self.show_auth_screen)

        frame = ctk.CTkFrame(self.container, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=30)

        ctk.CTkLabel(frame, text=self.t("generator.title"),
                     font=(FONT_FAMILY, 20, "bold")).pack(pady=(10, 18))

        self.gen_display = ctk.CTkEntry(frame, font=("Courier New", 22), height=56,
                                        justify="center")
        self.gen_display.pack(fill="x", pady=(0, 20))

        # --- Options ---
        self.gen_length_var = ctk.IntVar(value=18)
        self.gen_upper_var = ctk.BooleanVar(value=True)
        self.gen_digits_var = ctk.BooleanVar(value=True)
        self.gen_symbols_var = ctk.BooleanVar(value=True)

        options = ctk.CTkFrame(frame, fg_color=COLOR_BG_CARD, corner_radius=12)
        options.pack(fill="x", pady=(0, 18))

        length_label = ctk.CTkLabel(options, text=self.t("generator.length", n=18),
                                    font=(FONT_FAMILY, 13, "bold"))
        length_label.pack(anchor="w", padx=16, pady=(14, 0))

        def on_length(value):
            n = int(value)
            self.gen_length_var.set(n)
            length_label.configure(text=self.t("generator.length", n=n))
            # Debounce: the slider fires continuously while dragging.
            self._schedule_regenerate()

        slider = ctk.CTkSlider(options, from_=8, to=40, number_of_steps=32,
                               command=on_length)
        slider.set(18)
        slider.pack(fill="x", padx=16, pady=(2, 12))

        ctk.CTkCheckBox(options, text=self.t("generator.uppercase"), command=self.regenerate_password,
                        variable=self.gen_upper_var).pack(anchor="w", padx=16, pady=4)
        ctk.CTkCheckBox(options, text=self.t("generator.numbers"), command=self.regenerate_password,
                        variable=self.gen_digits_var).pack(anchor="w", padx=16, pady=4)
        ctk.CTkCheckBox(options, text=self.t("generator.symbols"), command=self.regenerate_password,
                        variable=self.gen_symbols_var).pack(anchor="w", padx=16, pady=(4, 14))

        # --- Action buttons ---
        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.pack(fill="x")
        ctk.CTkButton(actions, text=self.t("generator.regenerate"), height=42,
                      command=self.regenerate_password).pack(side="left", expand=True, padx=(0, 6))
        copy_btn = self._copy_button(actions, lambda: self.gen_display.get())
        copy_btn.configure(height=42, width=120)
        copy_btn.pack(side="left", expand=True, padx=(6, 0))

        self.regenerate_password()

    def _schedule_regenerate(self, delay=180):
        """Debounced regeneration, so dragging the slider isn't a flood."""
        if self._gen_after is not None:
            try:
                self.after_cancel(self._gen_after)
            except Exception:
                pass
        self._gen_after = self.after(delay, self.regenerate_password)

    def regenerate_password(self):
        self._gen_after = None
        # New token supersedes any animation still running from a prior call.
        self._gen_token += 1
        token = self._gen_token
        password = password_generator.generate_secure_password(
            length=self.gen_length_var.get(),
            use_upper=self.gen_upper_var.get(),
            use_digits=self.gen_digits_var.get(),
            use_symbols=self.gen_symbols_var.get(),
        )
        self.gen_display.configure(state="normal")
        self.animate_password(password, 0, token)

    def animate_password(self, target, step, token=None):
        # Apple-style "decryption" effect: scramble characters, then lock them
        # left-to-right. Hyphen group separators stay fixed throughout.
        # Stop if superseded by a newer password or the user navigated away.
        if token is not None and token != self._gen_token:
            return
        if not self.gen_display.winfo_exists() or self.current_view != "generator":
            return

        ANIMATION_DURATION = 0.8
        indices = [i for i, char in enumerate(target) if char != '-']
        total = len(indices)
        if total == 0:
            return

        total_animation_steps = total * 2
        interval = max(int((ANIMATION_DURATION / total_animation_steps) * 1000), 10)

        current_view = list(target)
        pool = password_generator.SCRAMBLE_POOL

        if step < total:
            # PHASE 1: all characters animate randomly
            for idx in indices:
                current_view[idx] = secrets.choice(pool)
        else:
            # PHASE 2: lock characters from left to right
            lock_index = step - total
            for i, idx in enumerate(indices):
                current_view[idx] = target[idx] if i <= lock_index else secrets.choice(pool)

        self.gen_display.delete(0, 'end')
        self.gen_display.insert(0, "".join(current_view))

        if step < total_animation_steps - 1:
            self.after(interval, lambda: self.animate_password(target, step + 1, token))
        else:
            self.gen_display.delete(0, 'end')
            self.gen_display.insert(0, target)
            self.gen_display.configure(state="readonly")