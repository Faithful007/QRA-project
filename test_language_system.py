#!/usr/bin/env python3
"""
Test script to verify language system functionality
"""

from src.translations import TRANSLATIONS, get_translation, get_available_languages

def test_translations():
    """Test that all translations are available."""
    print("=" * 70)
    print("Testing Language Translation System")
    print("=" * 70)
    
    languages = get_available_languages()
    
    print(f"\nAvailable Languages ({len(languages)}):")
    for code, name in languages.items():
        print(f"  {code}: {name}")
    
    # Test a few key strings
    test_strings = [
        "QRA Main Control",
        "Simulation",
        "Language",
        "Traffic Management",
        "HAR EVAC Analysis",
        "Cancel",
        "Program End",
    ]
    
    print(f"\nTesting Translation of {len(test_strings)} Strings in All Languages:")
    print("-" * 70)
    
    for lang_code, lang_name in languages.items():
        print(f"\n{lang_code.upper()}: {lang_name}")
        for text in test_strings:
            translated = get_translation(text, lang_code)
            # Only show if different from English
            if lang_code != "en":
                print(f"  '{text}' → '{translated}'")
    
    print("\n" + "=" * 70)
    print("Translation Statistics")
    print("=" * 70)
    
    for lang_code, lang_name in languages.items():
        count = len(TRANSLATIONS[lang_code])
        print(f"  {lang_code}: {count} translations")
    
    print(f"\nTotal unique English strings: {len(TRANSLATIONS['en'])}")

if __name__ == "__main__":
    test_translations()
    print("\n✓ Language system loaded successfully!")
