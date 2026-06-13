import os
import json

class LanguageManager:
    def __init__(self, filepath=None):
        # Resolve relative to this module so it works regardless of the current
        # working directory and inside a frozen (Nuitka/PyInstaller) build.
        if filepath is None:
            filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales.json")
        with open(filepath, "r", encoding="utf-8") as f:
            self.translations = json.load(f)

    def get_text(self, path, lang="en", **kwargs):
        """
        Retrieves a string using a dot-notated key (e.g., 'auth.title').
        Supports variable injection via kwargs.
        """
        keys = path.split('.')
        try:
            val = self.translations[lang]
            for key in keys:
                val = val[key]
            
            # Inject variables like {service} if present
            if isinstance(val, str) and kwargs:
                return val.format(**kwargs)
            return val
        except (KeyError, TypeError):
            return path # Fallback to the key itself if not found
    
    def get_supported_languages(self):
        """Returns a list of all language codes available in the JSON."""
        return list(self.translations.keys())