import json
import re
from pathlib import Path


class LinguisticAnalyzer:
    def __init__(self, lexicon_path: Path | None = None):
        if lexicon_path is None:
            lexicon_path = Path(__file__).resolve().parent.parent / "data" / "provocative_lexicon.json"

        with open(lexicon_path, "r", encoding="utf-8") as f:
            self.lexicon = json.load(f)

    def analyze(self, text: str) -> dict:
        clean_text = text.strip()
        if not clean_text:
            return {
                "linguistic_score": 0.0,
                "urgency_triggers": [],
                "conspiracy_triggers": [],
                "authority_triggers": [],
                "sara_triggers": [],
                "caps_ratio": 0.0,
                "exclamation_count": 0,
                "is_sensational": False,
            }

        text_lower = clean_text.lower()

        urgency_matches = [w for w in self.lexicon.get("urgency_triggers", []) if re.search(rf"\b{re.escape(w)}\b", text_lower)]
        conspiracy_matches = [w for w in self.lexicon.get("conspiracy_triggers", []) if re.search(rf"\b{re.escape(w)}\b", text_lower)]
        authority_matches = [w for w in self.lexicon.get("authority_impersonation", []) if re.search(rf"\b{re.escape(w)}\b", text_lower)]
        sara_matches = [w for w in self.lexicon.get("sara_polarization", []) if re.search(rf"\b{re.escape(w)}\b", text_lower)]

        alpha_chars = [c for c in clean_text if c.isalpha()]
        caps_chars = [c for c in alpha_chars if c.isupper()]
        caps_ratio = len(caps_chars) / len(alpha_chars) if alpha_chars else 0.0

        exclamations = len(re.findall(r"!{1,}", clean_text))
        questions = len(re.findall(r"\?{2,}", clean_text))

        trigger_weight = (
            (len(urgency_matches) * 0.25)
            + (len(conspiracy_matches) * 0.30)
            + (len(authority_matches) * 0.35)
            + (len(sara_matches) * 0.40)
        )

        style_weight = 0.0
        if caps_ratio > 0.35:
            style_weight += 0.25
        elif caps_ratio > 0.20:
            style_weight += 0.15

        if exclamations >= 2:
            style_weight += 0.20
        if questions >= 1:
            style_weight += 0.10

        combined_score = min(1.0, (trigger_weight * 0.6) + (style_weight * 0.4))

        return {
            "linguistic_score": round(combined_score, 3),
            "urgency_triggers": urgency_matches,
            "conspiracy_triggers": conspiracy_matches,
            "authority_triggers": authority_matches,
            "sara_triggers": sara_matches,
            "caps_ratio": round(caps_ratio, 3),
            "exclamation_count": exclamations,
            "is_sensational": combined_score >= 0.45,
        }
