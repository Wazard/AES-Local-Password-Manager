"""Lightweight master-password strength check (used at vault creation)."""
import re

LABELS = ["very weak", "weak", "fair", "good", "strong"]


def evaluate(password: str) -> dict:
    """Returns {score: 0-4, label, ok}. `ok` is the minimum to accept as a new
    master password (>= 8 chars and at least 'fair')."""
    classes = sum(bool(re.search(p, password)) for p in
                  (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
    score = 0
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if classes >= 2:
        score += 1
    if classes >= 3 and len(password) >= 10:
        score += 1
    score = min(score, 4)
    return {"score": score, "label": LABELS[score], "ok": len(password) >= 8 and score >= 2}
