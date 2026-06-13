"""Centralised colour palette, fonts and CustomTkinter theme overrides."""
import customtkinter as ctk

# --- Cozy palette (from the supplied swatches) ---
COLOR_SLATE = "#98B1BD"     # soft blue-gray – body text
COLOR_GOLD = "#C7A862"      # warm gold      – highlights (slider, checks)
COLOR_SAGE = "#878778"      # sage gray      – secondary actions
COLOR_STEEL = "#66769C"     # muted blue     – primary actions
COLOR_CHARCOAL = "#292929"  # near-black     – background

# Derived shades for surfaces / hovers
COLOR_BG = COLOR_CHARCOAL
COLOR_BG_CARD = "#363738"
COLOR_CARD_HOVER = "#43443F"
COLOR_TEXT = COLOR_SLATE      # labels / body text on the dark background
COLOR_BTN_TEXT = "#F2F4F5"    # near-white, readable on colored buttons
COLOR_MUTED = "#7E8C93"

COLOR_SUCCESS = COLOR_STEEL
COLOR_SUCCESS_HOVER = "#56638A"
COLOR_DANGER = "#A85751"      # warm muted red (no red in the palette)
COLOR_DANGER_HOVER = "#8F4843"
COLOR_ACCENT = COLOR_SAGE
COLOR_ACCENT_HOVER = "#75756A"
COLOR_GOLD_HOVER = "#B2954F"

FONT_FAMILY = "Segoe UI"


def apply_theme():
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
    tm["CTkButton"]["text_color"] = dual(COLOR_BTN_TEXT)

    tm["CTkEntry"]["fg_color"] = dual(COLOR_BG_CARD)
    tm["CTkEntry"]["border_color"] = dual(COLOR_BG_CARD)
    tm["CTkEntry"]["text_color"] = dual(COLOR_TEXT)
    tm["CTkEntry"]["placeholder_text_color"] = dual(COLOR_MUTED)

    tm["CTkOptionMenu"]["fg_color"] = dual(COLOR_ACCENT)
    tm["CTkOptionMenu"]["button_color"] = dual(COLOR_ACCENT_HOVER)
    tm["CTkOptionMenu"]["button_hover_color"] = dual(COLOR_STEEL)
    tm["CTkOptionMenu"]["text_color"] = dual(COLOR_BTN_TEXT)

    tm["DropdownMenu"]["fg_color"] = dual(COLOR_BG_CARD)
    tm["DropdownMenu"]["hover_color"] = dual(COLOR_ACCENT)
    tm["DropdownMenu"]["text_color"] = dual(COLOR_TEXT)

    tm["CTkCheckBox"]["fg_color"] = dual(COLOR_GOLD)
    tm["CTkCheckBox"]["hover_color"] = dual(COLOR_GOLD_HOVER)
    tm["CTkCheckBox"]["text_color"] = dual(COLOR_TEXT)
    tm["CTkCheckBox"]["checkmark_color"] = dual(COLOR_CHARCOAL)

    tm["CTkSlider"]["button_color"] = dual(COLOR_GOLD)
    tm["CTkSlider"]["button_hover_color"] = dual(COLOR_GOLD_HOVER)
    tm["CTkSlider"]["progress_color"] = dual(COLOR_STEEL)

    tm["CTkSegmentedButton"]["fg_color"] = dual(COLOR_BG_CARD)
    tm["CTkSegmentedButton"]["selected_color"] = dual(COLOR_STEEL)
    tm["CTkSegmentedButton"]["selected_hover_color"] = dual(COLOR_SUCCESS_HOVER)
    tm["CTkSegmentedButton"]["unselected_color"] = dual(COLOR_BG_CARD)
    tm["CTkSegmentedButton"]["unselected_hover_color"] = dual(COLOR_CARD_HOVER)
    tm["CTkSegmentedButton"]["text_color"] = dual(COLOR_BTN_TEXT)

    # Hide scrollbars: blend them into the background (still wheel-scrollable).
    tm["CTkScrollbar"]["fg_color"] = dual(COLOR_BG)
    tm["CTkScrollbar"]["button_color"] = dual(COLOR_BG)
    tm["CTkScrollbar"]["button_hover_color"] = dual(COLOR_BG)
