import json
import re
from pathlib import Path

# Peta singkatan / bahasa gaul medsos -> kata baku (dipakai normalize_slang).
# "tni" -> "tni" sengaja ada supaya singkatan resmi tidak tersentuh aturan lain.
SLANG_MAP = {
    "yg": "yang", "gk": "tidak", "ga": "tidak", "gak": "tidak", "nggak": "tidak",
    "ngga": "tidak", "tdk": "tidak", "kbr": "kabar", "dpt": "dapat", "dgn": "dengan",
    "utk": "untuk", "krn": "karena", "karna": "karena", "sdh": "sudah", "udh": "sudah",
    "blm": "belum", "bgt": "sangat", "jgn": "jangan", "tlg": "tolong", "mrk": "mereka",
    "org": "orang", "bnr": "benar", "beneran": "benaran", "kmrn": "kemarin",
    "skrg": "sekarang", "hrs": "harus", "bkn": "bukan", "gmn": "bagaimana",
    "emg": "memang", "trs": "terus", "ttg": "tentang", "tni": "tni",
}

# Huruf yang sering diganti angka untuk mengelabui pencarian ("b1ntara" -> "bintara").
LEET_MAP = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t"})


class LinguisticAnalyzer:
    def __init__(self, lexicon_path: Path | None = None):
        if lexicon_path is None:
            lexicon_path = Path(__file__).resolve().parent.parent / "data" / "provocative_lexicon.json"

        with open(lexicon_path, "r", encoding="utf-8") as f:
            self.lexicon = json.load(f)

    def normalize_slang(self, text: str) -> str:
        """Huruf kecil + rapikan huruf berulang + ubah slang/leetspeak jadi kata baku."""
        text = text.lower()
        # "heboooh" -> "heboh" (3+ huruf sama berurutan dijadikan 1)
        text = re.sub(r"([a-z])\1{2,}", r"\1", text)

        def fix(match: re.Match) -> str:
            tok = match.group(0)
            if tok in SLANG_MAP:
                return SLANG_MAP[tok]
            letters = sum(c.isalpha() for c in tok)
            digits = [c for c in tok if c.isdigit()]
            # Perbaiki leetspeak hanya jika token campuran huruf+angka, hurufnya >= 3,
            # dan SEMUA angkanya memang bisa dipetakan ("covid19" dibiarkan apa adanya).
            if letters >= 3 and digits and all(d in "013457" for d in digits):
                fixed = tok.translate(LEET_MAP)
                return SLANG_MAP.get(fixed, fixed)
            return tok

        return re.sub(r"[a-z0-9]+", fix, text)

    def analyze(self, text: str) -> dict:
        clean_text = text.strip()
        if not clean_text:
            return {
                "linguistic_score": 0.0,
                "urgency_triggers": [],
                "conspiracy_triggers": [],
                "authority_triggers": [],
                "sara_triggers": [],
                "anonymous_claim_triggers": [],
                "caps_ratio": 0.0,
                "exclamation_count": 0,
                "is_sensational": False,
            }

        # Teks dinormalisasi dulu (slang -> baku) sebelum dicocokkan ke leksikon.
        # caps_ratio tetap dihitung dari teks ASLI di bawah, karena huruf kapital hilang saat lowercase.
        text_lower = self.normalize_slang(clean_text)

        urgency_matches = [w for w in self.lexicon.get("urgency_triggers", []) if re.search(rf"\b{re.escape(w)}\b", text_lower)]
        conspiracy_matches = [w for w in self.lexicon.get("conspiracy_triggers", []) if re.search(rf"\b{re.escape(w)}\b", text_lower)]
        authority_matches = [w for w in self.lexicon.get("authority_impersonation", []) if re.search(rf"\b{re.escape(w)}\b", text_lower)]
        sara_matches = [w for w in self.lexicon.get("sara_polarization", []) if re.search(rf"\b{re.escape(w)}\b", text_lower)]

        # Klaim kabur tanpa atribusi jelas ("kata orang dalam", "kabar burung", ...)
        anonymous_matches = [w for w in self.lexicon.get("anonymous_claim_markers", []) if re.search(rf"\b{re.escape(w)}\b", text_lower)]

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
            + (len(anonymous_matches) * 0.20)
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
            "anonymous_claim_triggers": anonymous_matches,
            "caps_ratio": round(caps_ratio, 3),
            "exclamation_count": exclamations,
            "is_sensational": combined_score >= 0.45,
        }