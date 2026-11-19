"""Animated, configurable password generator screen."""
import math
import secrets
import customtkinter as ctk

from core import password_generator
from UI import components as ui
from UI import theme as T

ANIMATION_DURATION = 0.8  # seconds for the full scramble-and-lock effect


def _entropy_bits(length, use_upper, use_digits, use_symbols):
    charset = len(password_generator.LOWERCASE)
    if use_upper:
        charset += len(password_generator.UPPERCASE)
    if use_digits:
        charset += len(password_generator.DIGITS)
    if use_symbols:
        charset += len(password_generator.SYMBOLS)
    return int(length * math.log2(charset))


def _score_for_bits(bits):
    for limit, score in ((45, 0), (60, 1), (80, 2), (100, 3)):
        if bits < limit:
            return score
    return 4


class GeneratorMixin:
    def show_gen_pass_screen(self):
        self.current_view = "generator"
        self.clear_screen()
        ui.app_bar(self, back=self.show_dashboard if self.logged_in else self.show_auth_screen,
                   show_nav=self.logged_in)

        body = ui.page(self)
        ui.title(body, self.t("generator.title")).pack(pady=(0, T.GAP_L))

        self.gen_display = ctk.CTkEntry(
            body, font=T.mono(T.S_DISPLAY), height=64, justify="center",
            fg_color=T.CARD, border_color=T.BORDER, border_width=T.BORDER_W,
            corner_radius=T.R_CARD, text_color=T.TEXT)
        self.gen_display.pack(fill="x")

        self.gen_meter = ui.StrengthMeter(body)
        self.gen_meter.pack(fill="x", pady=(T.GAP, T.GAP_L))

        # --- Options ---
        self.gen_length_var = ctk.IntVar(value=18)
        self.gen_upper_var = ctk.BooleanVar(value=True)
        self.gen_digits_var = ctk.BooleanVar(value=True)
        self.gen_symbols_var = ctk.BooleanVar(value=True)

        options = ui.card(body)
        options.pack(fill="x")

        length_row = ctk.CTkFrame(options, fg_color="transparent")
        length_row.pack(fill="x", padx=T.PAD_CARD, pady=(T.PAD_CARD, 0))
        length_label = ctk.CTkLabel(length_row, text=self.t("generator.length", n=18),
                                    font=T.font(T.S_BODY, "bold"), text_color=T.TEXT)
        length_label.pack(side="left")

        def on_length(value):
            n = int(value)
            self.gen_length_var.set(n)
            length_label.configure(text=self.t("generator.length", n=n))
            # Debounce: the slider fires continuously while dragging.
            self._schedule_regenerate()

        slider = ctk.CTkSlider(options, from_=8, to=40, number_of_steps=32,
                               command=on_length, height=18, button_length=6)
        slider.set(18)
        slider.pack(fill="x", padx=T.PAD_CARD, pady=(T.GAP_S, 0))

        ends = ctk.CTkFrame(options, fg_color="transparent")
        ends.pack(fill="x", padx=T.PAD_CARD)
        ctk.CTkLabel(ends, text="8", font=T.font(T.S_SMALL),
                     text_color=T.TEXT_MUTED).pack(side="left")
        ctk.CTkLabel(ends, text="40", font=T.font(T.S_SMALL),
                     text_color=T.TEXT_MUTED).pack(side="right")

        checks = ctk.CTkFrame(options, fg_color="transparent")
        checks.pack(fill="x", padx=T.PAD_CARD, pady=(T.GAP, T.PAD_CARD))
        checks.grid_columnconfigure((0, 1, 2), weight=1, uniform="opt")
        for col, (key, var) in enumerate((
                ("generator.uppercase", self.gen_upper_var),
                ("generator.numbers", self.gen_digits_var),
                ("generator.symbols", self.gen_symbols_var))):
            ctk.CTkCheckBox(checks, text=self.t(key), variable=var,
                            command=self.regenerate_password,
                            font=T.font(T.S_LABEL), checkbox_width=18,
                            checkbox_height=18).grid(row=0, column=col, sticky="w")

        # --- Action buttons ---
        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(fill="x", pady=(T.GAP_L, T.GAP_L))
        ui.secondary_button(actions, self.t("generator.regenerate"),
                            self.regenerate_password, height=42).pack(
                                side="left", expand=True, fill="x", padx=(0, T.GAP_S))
        ui.copy_button(self, actions, lambda: self.gen_display.get(),
                       style="primary", height=42, width=150).pack(
                           side="left", expand=True, fill="x", padx=(T.GAP_S, 0))

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
        length = self.gen_length_var.get()
        password = password_generator.generate_secure_password(
            length=length,
            use_upper=self.gen_upper_var.get(),
            use_digits=self.gen_digits_var.get(),
            use_symbols=self.gen_symbols_var.get(),
        )
        bits = _entropy_bits(length, self.gen_upper_var.get(),
                             self.gen_digits_var.get(), self.gen_symbols_var.get())
        score = _score_for_bits(bits)
        self.gen_meter.set(score, self.t("generator.strength",
                                         label=self.t("strength.%d" % score),
                                         n=bits))
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
        # Scrambling reads as "working"; the settled password is full contrast.
        self.gen_display.configure(
            text_color=T.TEXT if step >= total_animation_steps - 1 else T.TEXT_SECONDARY)

        if step < total_animation_steps - 1:
            self.after(interval, lambda: self.animate_password(target, step + 1, token))
        else:
            self.gen_display.delete(0, 'end')
            self.gen_display.insert(0, target)
            self.gen_display.configure(state="readonly", text_color=T.TEXT)
