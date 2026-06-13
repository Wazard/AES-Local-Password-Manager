"""Animated, configurable password generator screen."""
import secrets
import customtkinter as ctk

from core import password_generator
from UI.theme import FONT_FAMILY, COLOR_BG_CARD
from UI.components import copy_button, back_button

ANIMATION_DURATION = 0.8  # seconds for the full scramble-and-lock effect


class GeneratorMixin:
    def show_gen_pass_screen(self):
        self.current_view = "generator"
        self.clear_screen()
        back_button(self, self.show_dashboard if self.logged_in else self.show_auth_screen)

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

        slider = ctk.CTkSlider(options, from_=8, to=40, number_of_steps=32, command=on_length)
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
        copy_btn = copy_button(self, actions, lambda: self.gen_display.get())
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
