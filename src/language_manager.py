"""
Language Manager for QRA Program
Handles language switching and translation signals
"""

from PyQt6.QtCore import QObject, pyqtSignal
from .translations import get_translation, get_available_languages


class LanguageManager(QObject):
    """Centralized language manager with signal-based updates."""
    
    # Signal emitted when language changes: emits language code (e.g., 'en', 'ko')
    language_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self._current_language = "en"
    
    def set_language(self, language_code: str) -> None:
        """
        Set the current language and emit signal for all UI components to update.
        
        Args:
            language_code: Language code ('en', 'ko', 'ja', 'de', 'it', 'fr', 'nl')
        """
        if language_code != self._current_language:
            self._current_language = language_code
            self.language_changed.emit(language_code)
    
    def get_language(self) -> str:
        """Get the current language code."""
        return self._current_language
    
    def translate(self, text: str, default: str = "") -> str:
        """
        Translate text to current language.
        
        Args:
            text: Text to translate (English key)
            default: Default text if translation not found
            
        Returns:
            Translated text or original text if translation not found
        """
        translation = get_translation(text, self._current_language)
        return translation if translation else (default if default else text)
    
    def get_available_languages(self) -> dict:
        """Get dictionary of available languages."""
        return get_available_languages()
    
    def get_language_name(self, language_code: str) -> str:
        """Get display name for a language code."""
        languages = self.get_available_languages()
        return languages.get(language_code, language_code)


# Global language manager instance
_language_manager = None


def get_language_manager() -> LanguageManager:
    """Get or create the global language manager instance."""
    global _language_manager
    if _language_manager is None:
        _language_manager = LanguageManager()
    return _language_manager


def translate(text: str, default: str = "") -> str:
    """
    Convenience function to translate text using the global language manager.
    
    Args:
        text: Text to translate
        default: Default text if translation not found
        
    Returns:
        Translated text
    """
    return get_language_manager().translate(text, default)
