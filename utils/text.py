# utils/text.py
import re, unicodedata

def normalize(text: str) -> str:
    """Quita tildes, múltiplos espacios y pasa a minúsculas ASCII."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")  # á -> a, ñ -> n
    text = re.sub(r"\s+", " ", text)                      # colapsa espacios
    return text.strip().lower()
