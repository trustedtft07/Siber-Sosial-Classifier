import re
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
            }

        detected_domains = []
        is_tier_1 = False
        is_suspicious = False

        for raw_url in found_urls:
            parsed = urlparse(raw_url)
            domain = parsed.netloc.lower()
            detected_domains.append(domain)

            if any(domain == t1 or domain.endswith("." + t1) for t1 in self.TIER_1_DOMAINS):
                is_tier_1 = True

            if any(domain.endswith(tld) for tld in self.SUSPICIOUS_TLDS) or re.search(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", domain):
                is_suspicious = True

        if is_suspicious:
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
            "detected_domains": list(set(detected_domains)),
            "source_tier": tier,
            "source_risk": round(risk, 2),
            "is_chain_message": is_chain_message,
            "notes": notes,
        }
