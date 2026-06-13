"""Windows system-tray integration. Degrades gracefully when pystray/Pillow
are not installed (the login toggle simply disables itself)."""
import threading

from UI.theme import COLOR_CHARCOAL

try:
    import pystray
    from PIL import Image
    TRAY_AVAILABLE = True
except Exception:
    TRAY_AVAILABLE = False


class TrayManager:
    """Owns the pystray icon lifecycle for a CTk window.

    `label_getter` is a callable mapping a translation key (e.g. "tray.open")
    to the localised label, so the menu follows the app's current language.
    """

    def __init__(self, window, icon_path, label_getter):
        self.window = window
        self.icon_path = icon_path
        self.labels = label_getter
        self.icon = None

    def hide(self):
        """Withdraw the window to the tray, creating the icon on first use."""
        self.window.withdraw()
        if self.icon is None:
            self._create_icon()

    def _create_icon(self):
        try:
            image = Image.open(self.icon_path)
        except Exception:
            image = Image.new("RGB", (64, 64), COLOR_CHARCOAL)
        menu = pystray.Menu(
            pystray.MenuItem(self.labels("tray.open"), self._on_open, default=True),
            pystray.MenuItem(self.labels("tray.quit"), self._on_quit),
        )
        self.icon = pystray.Icon("secure_vault", image, "Secure Vault", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    # Tray callbacks run off the main thread; bounce back to the Tk loop.
    def _on_open(self, icon=None, item=None):
        self.window.after(0, self._restore)

    def _on_quit(self, icon=None, item=None):
        self.window.after(0, self.shutdown)

    def _restore(self):
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def stop(self):
        if self.icon is not None:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None

    def shutdown(self):
        self.stop()
        self.window.destroy()
