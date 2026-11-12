import re
from difflib import SequenceMatcher
from urllib.parse import urlparse


class SourceVerifier:
    TIER_1_DOMAINS = {
        "mil.id",
        "go.id",
        "antaranews.com",
        "kompas.com",
        "detik.com",
        "tempo.co",
        "turnbackhoax.id",
        "cekfakta.com",
        "republika.co.id",
    }

    SUSPICIOUS_TLDS = {".xyz", ".top", ".club", ".click", ".link", ".apk", ".work"}

    # ---- Deteksi domain tiruan (typosquatting) -------------------------------------------
    # Domain resmi yang sering ditiru. Dipakai untuk uji kemiripan.
    PROTECTED_DOMAINS = (
        "tniad.mil.id", "tni.mil.id", "kemhan.go.id", "komdigi.go.id", "bssn.go.id",
        "kompas.com", "detik.com", "antaranews.com", "tempo.co",
        "turnbackhoax.id", "cekfakta.com", "republika.co.id",
    )

    # Nama instansi/media -> domain resminya. Jika nama ini muncul di domain yang BUKAN resmi,
    # dianggap meniru. Nama panjang dicari sebagai potongan teks; nama pendek ("tni", "bssn")
    # harus berdiri sebagai satu kata utuh supaya tidak salah tangkap.
    BRAND_SUBSTRINGS = {
        "tniad": "tniad.mil.id", "dispenad": "tniad.mil.id", "pussiberad": "tniad.mil.id",
        "mabesad": "tniad.mil.id", "kemhan": "kemhan.go.id", "komdigi": "komdigi.go.id",
        "kompas": "kompas.com", "antaranews": "antaranews.com",
        "turnbackhoax": "turnbackhoax.id", "cekfakta": "cekfakta.com", "republika": "republika.co.id",
    }
    BRAND_TOKENS = {"tni": "tni.mil.id", "bssn": "bssn.go.id"}

    # Domain asli milik kelompok media yang sama namun bukan domain Tier 1; jangan dituduh tiruan.
    # (Tetap dinilai seperti biasa, yaitu Tier 2.) Daftar ini perlu dicek tim.
    LEGIT_LOOKALIKES = {"kompas.id", "kompas.tv", "kompasiana.com"}

    SIMILARITY_THRESHOLD = 0.75
    TYPOSQUAT_RISK = 0.95

    @staticmethod
    def _squash(host: str) -> str:
        """Buang titik/strip/underscore supaya 'tniad-mil.com' dibandingkan sebagai 'tniadmilcom'."""
        return re.sub(r"[.\-_]", "", host)

    def _is_tier_1(self, host: str) -> bool:
        return any(host == t1 or host.endswith("." + t1) for t1 in self.TIER_1_DOMAINS)

    def _check_typosquat(self, host: str) -> dict | None:
        """Kembalikan info tiruan jika host terlihat meniru domain resmi, selain itu None."""
        host = host[4:] if host.startswith("www.") else host

        if not host or self._is_tier_1(host):
            return None
        if any(host == d or host.endswith("." + d) for d in self.LEGIT_LOOKALIKES):
            return None

        # Cara 1: memuat nama instansi/media resmi padahal bukan domain resminya.
        labels = set(re.split(r"[.\-_]", host))
        for brand, official in self.BRAND_SUBSTRINGS.items():
            if brand in host:
                return {"domain": host, "mimics": official, "method": "brand_keyword", "similarity": None}
        for brand, official in self.BRAND_TOKENS.items():
            if brand in labels:
                return {"domain": host, "mimics": official, "method": "brand_keyword", "similarity": None}

        # Cara 2: ejaannya sangat mirip dengan domain resmi (typo, strip, huruf dobel).
        squashed = self._squash(host)
        best, best_ratio = None, 0.0
        for official in self.PROTECTED_DOMAINS:
            ratio = SequenceMatcher(None, squashed, self._squash(official)).ratio()
            if ratio > best_ratio:
                best, best_ratio = official, ratio
        if best and best_ratio >= self.SIMILARITY_THRESHOLD:
            return {"domain": host, "mimics": best, "method": "similarity", "similarity": round(best_ratio, 2)}

        return None

    # ---------------------------------------------------------------------------------------
    def verify(self, text: str, explicit_url: str | None = None) -> dict:
        found_urls = re.findall(r"https?://[^\s]+", text)
        if explicit_url:
            found_urls.append(explicit_url)

        is_chain_message = bool(
            re.search(r"(diteruskan berkali-kali|forwarded many times|broadcast dari grup|copas dari)", text, re.I)
        )

        if not found_urls:
            return {
                "has_url": False,
                "detected_domains": [],
                "source_tier": "TIER_3_UNATTRIBUTED" if is_chain_message else "TIER_2_UNKNOWN",
                "source_risk": 0.65 if is_chain_message else 0.40,
                "is_chain_message": is_chain_message,
                "notes": "Pesan berantai tanpa rujukan tautan kredibel." if is_chain_message else "Teks tidak menyertakan tautan sumber.",
                "typosquat_matches": [],
            }

        detected_domains = []
        typosquat_matches = []
        is_tier_1 = False
        is_suspicious = False

        for raw_url in found_urls:
            try:
                # hostname membuang port dan "user@" di depan, jadi trik
                # "https://tniad.mil.id@situs-jahat.com" tidak lagi dianggap domain resmi.
                domain = (urlparse(raw_url).hostname or "").lower().rstrip(".")
            except ValueError:
                continue
            if not domain:
                continue
            detected_domains.append(domain)

            if self._is_tier_1(domain):
                is_tier_1 = True

            squat = self._check_typosquat(domain)
            if squat:
                typosquat_matches.append(squat)

            if any(domain.endswith(tld) for tld in self.SUSPICIOUS_TLDS) or re.search(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", domain):
                is_suspicious = True

        if typosquat_matches:
            tier = "TIER_3_SUSPICIOUS"
            risk = self.TYPOSQUAT_RISK
            first = typosquat_matches[0]
            notes = f"Terindikasi domain tiruan (typosquatting): '{first['domain']}' meniru '{first['mimics']}'."
        elif is_suspicious:
            tier = "TIER_3_SUSPICIOUS"
            risk = 0.90
            notes = "Ditemukan tautan dengan domain mencurigakan atau indikasi phishing."
        elif is_tier_1:
            tier = "TIER_1_VERIFIED"
            risk = 0.10
            notes = "Tautan merujuk pada domain resmi pemerintah, militer, atau media arus utama."
        else:
            tier = "TIER_2_EXTERNAL"
            risk = 0.50
            notes = "Tautan berasal dari platform publik umum atau blog yang belum terverifikasi."

        return {
            "has_url": True,
            "detected_domains": list(dict.fromkeys(detected_domains)),
            "source_tier": tier,
            "source_risk": round(risk, 2),
            "is_chain_message": is_chain_message,
            "notes": notes,
            "typosquat_matches": typosquat_matches,
        }