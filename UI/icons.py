"""Loads PNG icons from the images/ folder as CTkImage objects (cached).

Resolved relative to the project root so it works from source and from a
frozen build (the images/ folder is bundled as data)."""
import os
import customtkinter as ctk
from PIL import Image

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images")
_cache = {}


def load(name, size):
    key = (name, size)
    if key not in _cache:
        img = Image.open(os.path.join(_DIR, name)).convert("RGBA")
        _cache[key] = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    return _cache[key]


def load_dimmed(name, size, alpha=0.30):
    """A faded version (reduced opacity) — used for the inactive star state."""
    key = (name, size, "dim")
    if key not in _cache:
        img = Image.open(os.path.join(_DIR, name)).convert("RGBA")
        faded = img.split()[3].point(lambda p: int(p * alpha))
        img.putalpha(faded)
        _cache[key] = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    return _cache[key]


def _hex_to_rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def load_tinted(name, size, color):
    """Recolor an icon to `color`, keeping its shape (uses the alpha as a mask).
    Works no matter what colour the source pixels are."""
    key = (name, size, "tint", color)
    if key not in _cache:
        img = Image.open(os.path.join(_DIR, name)).convert("RGBA")
        r, g, b = _hex_to_rgb(color)
        tinted = Image.new("RGBA", img.size, (r, g, b, 0))
        tinted.putalpha(img.split()[3])
        _cache[key] = ctk.CTkImage(light_image=tinted, dark_image=tinted, size=(size, size))
    return _cache[key]


def exists(name):
    return os.path.exists(os.path.join(_DIR, name))
