"""Design tokens, loaded from UI/palette.json.

Everything visual — colours, font families, sizes, radii, spacing — comes from
that JSON file, so a different palette can be tried by editing it and
restarting the app. This module turns those tokens into module-level constants
and pushes them into CustomTkinter's theme manager.
"""
import json
import os
import tkinter.font as tkfont

import customtkinter as ctk

PALETTE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "palette.json")

with open(PALETTE_FILE, encoding="utf-8") as _fh:
    PALETTE = json.load(_fh)

C = PALETTE["colors"]
_F = PALETTE["fonts"]
M = PALETTE["metrics"]

PALETTE_NAME = PALETTE.get("name", "custom")

# --- Colours -------------------------------------------------------------
BG = C["bg_window"]
BG_BAR = C["bg_bar"]
CARD = C["bg_card"]
CARD_HOVER = C["bg_card_hover"]
INPUT_BG = C["bg_input"]
INPUT_BG_FOCUS = C["bg_input_focus"]

BORDER = C["border_subtle"]
BORDER_STRONG = C["border_strong"]

TEXT = C["text_primary"]
TEXT_SECONDARY = C["text_secondary"]
TEXT_MUTED = C["text_muted"]

PRIMARY = C["primary"]
PRIMARY_HOVER = C["primary_hover"]
PRIMARY_SUBTLE = C["primary_subtle"]
ON_PRIMARY = C["text_on_primary"]

SECONDARY = C["secondary"]
SECONDARY_HOVER = C["secondary_hover"]
ON_SECONDARY = C["text_on_secondary"]

DANGER = C["danger"]
DANGER_HOVER = C["danger_hover"]
ON_DANGER = C["text_on_danger"]

ACCENT = C["accent"]
ACCENT_HOVER = C["accent_hover"]

POSITIVE = C["positive"]
WARNING = C["warning"]
NEGATIVE = C["negative"]

TRACK = C["track"]

STRENGTH_COLORS = [C["strength_0"], C["strength_1"], C["strength_2"],
                   C["strength_3"], C["strength_4"]]

# --- Metrics -------------------------------------------------------------
R_CARD = M["radius_card"]
R_BTN = M["radius_button"]
R_INPUT = M["radius_input"]
R_PILL = M["radius_pill"]

H_BAR = M["height_bar"]
H_BTN = M["height_button"]
H_INPUT = M["height_input"]
H_ROW = M["height_row"]
H_CARD = M["height_card"]

PAD_SCREEN = M["pad_screen"]
PAD_CARD = M["pad_card"]
GAP_S = M["gap_small"]
GAP = M["gap"]
GAP_L = M["gap_large"]
BORDER_W = M["border_width"]

WINDOW_W = M["window_width"]
WINDOW_H = M["window_height"]
WINDOW_MIN_W = M["window_min_width"]
WINDOW_MIN_H = M["window_min_height"]


# Font families are resolved lazily: tkfont.families() needs a live Tk root,
# which does not exist yet when this module is imported.
FONT_FAMILY = _F["ui_fallback"]
MONO_FAMILY = _F["mono_fallback"]
_resolved = {}


def _family(kind):
    """Uses the preferred font only if Windows actually has it installed."""
    if kind not in _resolved:
        preferred, fallback = ((_F["ui"], _F["ui_fallback"]) if kind == "ui"
                               else (_F["mono"], _F["mono_fallback"]))
        try:
            chosen = preferred if preferred in tkfont.families() else fallback
        except Exception:
            return fallback  # no root yet - don't cache this answer
        _resolved[kind] = chosen
        globals()["FONT_FAMILY" if kind == "ui" else "MONO_FAMILY"] = chosen
    return _resolved[kind]

S_TITLE = _F["size_title"]
S_HEADING = _F["size_heading"]
S_BODY = _F["size_body"]
S_LABEL = _F["size_label"]
S_SMALL = _F["size_small"]
S_MONO = _F["size_mono"]
S_DISPLAY = _F["size_display"]


def font(size=None, weight="normal"):
    return (_family("ui"), size or S_BODY, weight)


def mono(size=None, weight="normal"):
    return (_family("mono"), size or S_MONO, weight)


def apply_theme():
    """Pushes the palette into CustomTkinter so stock widgets match."""
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")
    tm = ctk.ThemeManager.theme

    def dual(c):
        return [c, c]

    tm["CTk"]["fg_color"] = dual(BG)
    tm["CTkToplevel"]["fg_color"] = dual(BG)
    tm["CTkFrame"]["fg_color"] = dual(BG)
    tm["CTkFrame"]["top_fg_color"] = dual(CARD)
    tm["CTkFrame"]["border_color"] = dual(BORDER)

    tm["CTkLabel"]["text_color"] = dual(TEXT)

    tm["CTkButton"]["fg_color"] = dual(SECONDARY)
    tm["CTkButton"]["hover_color"] = dual(SECONDARY_HOVER)
    tm["CTkButton"]["text_color"] = dual(ON_SECONDARY)
    tm["CTkButton"]["border_color"] = dual(BORDER)
    tm["CTkButton"]["corner_radius"] = R_BTN

    tm["CTkEntry"]["fg_color"] = dual(INPUT_BG)
    tm["CTkEntry"]["border_color"] = dual(BORDER)
    tm["CTkEntry"]["text_color"] = dual(TEXT)
    tm["CTkEntry"]["placeholder_text_color"] = dual(TEXT_MUTED)
    tm["CTkEntry"]["corner_radius"] = R_INPUT
    tm["CTkEntry"]["border_width"] = BORDER_W

    tm["CTkOptionMenu"]["fg_color"] = dual(SECONDARY)
    tm["CTkOptionMenu"]["button_color"] = dual(SECONDARY_HOVER)
    tm["CTkOptionMenu"]["button_hover_color"] = dual(BORDER_STRONG)
    tm["CTkOptionMenu"]["text_color"] = dual(ON_SECONDARY)
    tm["CTkOptionMenu"]["corner_radius"] = R_BTN

    tm["DropdownMenu"]["fg_color"] = dual(CARD)
    tm["DropdownMenu"]["hover_color"] = dual(CARD_HOVER)
    tm["DropdownMenu"]["text_color"] = dual(TEXT)

    tm["CTkCheckBox"]["fg_color"] = dual(PRIMARY)
    tm["CTkCheckBox"]["hover_color"] = dual(PRIMARY_HOVER)
    tm["CTkCheckBox"]["border_color"] = dual(BORDER_STRONG)
    tm["CTkCheckBox"]["text_color"] = dual(TEXT_SECONDARY)
    tm["CTkCheckBox"]["checkmark_color"] = dual(ON_PRIMARY)

    tm["CTkSlider"]["fg_color"] = dual(TRACK)
    tm["CTkSlider"]["button_color"] = dual(PRIMARY)
    tm["CTkSlider"]["button_hover_color"] = dual(PRIMARY_HOVER)
    tm["CTkSlider"]["progress_color"] = dual(PRIMARY)

    tm["CTkProgressBar"]["fg_color"] = dual(TRACK)
    tm["CTkProgressBar"]["progress_color"] = dual(PRIMARY)
    tm["CTkProgressBar"]["border_color"] = dual(BORDER)

    tm["CTkSegmentedButton"]["fg_color"] = dual(SECONDARY)
    tm["CTkSegmentedButton"]["selected_color"] = dual(PRIMARY)
    tm["CTkSegmentedButton"]["selected_hover_color"] = dual(PRIMARY_HOVER)
    tm["CTkSegmentedButton"]["unselected_color"] = dual(SECONDARY)
    tm["CTkSegmentedButton"]["unselected_hover_color"] = dual(SECONDARY_HOVER)
    tm["CTkSegmentedButton"]["text_color"] = dual(ON_SECONDARY)

    tm["CTkScrollbar"]["fg_color"] = dual(BG)
    tm["CTkScrollbar"]["button_color"] = dual(BORDER)
    tm["CTkScrollbar"]["button_hover_color"] = dual(BORDER_STRONG)
