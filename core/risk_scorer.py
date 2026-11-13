import re

# Aktif hanya jika (1) entri terdekat berstatus BENAR dan isinya tentang layanan tanpa biaya, dan
# (2) teks input meminta uang/biaya di klausa yang tidak mengandung penyangkalan atau peringatan.
FREE_SERVICE_RE = re.compile(
    r"gratis|tidak dipungut|tanpa biaya|tidak ada biaya|bebas biaya|tanpa sepeser|calo|percaloan|pungutan", re.I
)
FEE_CUE_RE = re.compile(
    r"\b(bayar|membayar|pembayaran|transfer|rekening|setor|menyetor|uang|biaya|pungutan|administrasi|dana|pelicin|"
    r"rp\.?\s?\d+|\d[\d.,]*\s?(?:juta|ribu|jt|rb))\b",
    re.I,
)
# Klausa yang menyangkal/memperingatkan ("tidak dipungut biaya", "jangan transfer uang", "waspada calo") diabaikan.
NEGATION_RE = re.compile(
    r"\b(jangan|waspada|hati-hati|awas|gratis|bebas biaya|tanpa|melapor|laporkan|melaporkan|"
    r"diproses hukum|proses hukum|ditindak|ditangkap|dipidana|sanksi|pemberhentian|tidak ditoleransi|tidak mentolerir)\b"
    r"|\b(tidak|bukan)\s+(perlu\s+|boleh\s+|usah\s+|akan\s+|pernah\s+|ada\s+)?"
    r"(me|mem|men|di|ter)?(transfer|bayar|setor|pungut|kenakan|minta|kirim|biaya|uang)\w*",
    re.I,
)
CLAUSE_SPLIT_RE = re.compile(r"[.;!?\n,]| dan | namun | tetapi | sedangkan ", re.I)


class RiskScorer:
    WEIGHT_LINGUISTIC = 0.30
    WEIGHT_EVIDENCE = 0.45
    WEIGHT_SOURCE = 0.25

    MATCH_THRESHOLD = 0.30      # kemiripan minimal agar dianggap "cocok" dengan arsip
    WEAK_MATCH_START = 0.15     # di bawah ini kemiripan dianggap kebetulan (tidak ada kredit)
    NO_EVIDENCE_RISK = 0.35     # risiko netral bila tidak ada bukti yang cocok

    CONTRADICTION_EVIDENCE_RISK = 0.80
    CONTRADICTION_FLOOR = 0.50  # skor minimal 50 = MISLEADING / PROVOKATIF

    ZERO_DAY_MAX_SIMILARITY = 0.25
    ZERO_DAY_MIN_RISK = 0.70
    ZERO_DAY_FLOOR = 0.45  # = batas bawah status MISLEADING / PROVOKATIF

    def calculate(self, linguistic_data: dict, evidence_data: list[dict], source_data: dict, raw_text: str) -> dict:
        linguistic_score = linguistic_data.get("linguistic_score", 0.0)
        source_risk = source_data.get("source_risk", 0.40)

        best_match = evidence_data[0] if evidence_data else None
        sim_score = best_match.get("similarity_score", 0.0) if best_match else 0.0
        verdict = best_match.get("verdict", "TIDAK_DIKETAHUI") if best_match else "TIDAK_DIKETAHUI"

        if sim_score >= self.MATCH_THRESHOLD:
            if verdict == "SALAH":
                evidence_risk = min(1.0, 0.70 + (sim_score * 0.30))
            elif verdict == "MISLEADING":
                evidence_risk = min(1.0, 0.50 + (sim_score * 0.35))
            elif verdict == "BENAR":
                evidence_risk = max(0.02, 0.15 - (sim_score * 0.15))
            else:
                evidence_risk = 0.45
        elif sim_score >= self.WEAK_MATCH_START and verdict in ("SALAH", "MISLEADING"):
            # Kemiripan lemah dengan klaim yang SUDAH terbukti salah: naik landai dari 0.35 (tidak ada bukti)
            # ke nilai pada batas cocok, supaya selisih 0.01 tidak membuat risikonya melompat.
            # Sengaja TIDAK berlaku untuk BENAR: kemiripan lemah dengan berita asli tidak boleh menurunkan risiko.
            top = (0.70 + self.MATCH_THRESHOLD * 0.30) if verdict == "SALAH" else (0.50 + self.MATCH_THRESHOLD * 0.35)
            fraction = (sim_score - self.WEAK_MATCH_START) / (self.MATCH_THRESHOLD - self.WEAK_MATCH_START)
            evidence_risk = self.NO_EVIDENCE_RISK + fraction * (top - self.NO_EVIDENCE_RISK)
        else:
            evidence_risk = self.NO_EVIDENCE_RISK

        # Penjaga kontradiksi: cocok dengan berita BENAR "tanpa biaya", padahal teks meminta pembayaran.
        fact_contradiction = bool(
            verdict == "BENAR"
            and sim_score >= self.MATCH_THRESHOLD
            and self._contradicts_free_claim(raw_text, best_match)
        )
        fact_contradiction_note = None
        if fact_contradiction:
            evidence_risk = max(evidence_risk, self.CONTRADICTION_EVIDENCE_RISK)
            fact_contradiction_note = (
                f"Teks meminta pembayaran/biaya, bertentangan dengan arsip resmi {best_match.get('id')} "
                f"yang menyatakan layanan tersebut tanpa biaya."
            )

        final_composite = (
            (self.WEIGHT_LINGUISTIC * linguistic_score)
            + (self.WEIGHT_EVIDENCE * evidence_risk)
            + (self.WEIGHT_SOURCE * source_risk)
        )

        if sim_score >= 0.65 and verdict == "SALAH":
            final_composite = max(final_composite, 0.78)

        # Zero-Day Rumor: isu baru yang belum ada di database (kemiripan rendah), tetapi gaya bahasa
        # DAN sumbernya sama-sama sangat mencurigakan. Minimal dinaikkan ke MISLEADING / PROVOKATIF
        # (skor >= 45), supaya tidak lolos hanya karena belum ada klarifikasinya.
        zero_day_rumor = (
            sim_score < self.ZERO_DAY_MAX_SIMILARITY
            and linguistic_score > self.ZERO_DAY_MIN_RISK
            and source_risk > self.ZERO_DAY_MIN_RISK
        )
        if zero_day_rumor:
            final_composite = max(final_composite, self.ZERO_DAY_FLOOR)

        # Kontradiksi dengan fakta resmi: minimal MISLEADING / PROVOKATIF (bukan langsung HOAX, karena
        # deteksinya berbasis aturan kata dan keputusan akhir tetap di analis).
        if fact_contradiction:
            final_composite = max(final_composite, self.CONTRADICTION_FLOOR)

        scaled_score = round(final_composite * 100, 1)

        if scaled_score >= 70.0:
            classification = "HOAX / DISINFORMASI"
            threat_level = "KRITIS"
            action_code = "RED_FLAG_TAKEDOWN_COUNTER"
        elif scaled_score >= 45.0:
            classification = "MISLEADING / PROVOKATIF"
            threat_level = "TINGGI"
            action_code = "MONITOR_FACTCHECK_CLARIFICATION"
        elif scaled_score >= 25.0:
            classification = "PERLU VERIFIKASI (BELUM TERBUKTI)"
            threat_level = "SEDANG"
            action_code = "NEED_FURTHER_VERIFICATION"
        else:
            classification = "VALID / TERKONFIRMASI"
            threat_level = "RENDAH"
            action_code = "CLEAR_STATUS"

        matched_entry = best_match if sim_score >= 0.25 else None
        if fact_contradiction:
            threat_domain = "Penipuan Siber & Scam"  # meminta uang atas nama layanan resmi = modus penipuan
        else:
            threat_domain = self._determine_threat_domain(
                raw_text, linguistic_data, matched_entry, scaled_score
            )

        return {
            "score": scaled_score,
            "classification": classification,
            "threat_level": threat_level,
            "threat_domain": threat_domain,
            "action_code": action_code,
            "sub_scores": {
                "linguistic_score": round(linguistic_score * 100, 1),
                "evidence_risk": round(evidence_risk * 100, 1),
                "source_risk": round(source_risk * 100, 1),
            },
            "best_match": matched_entry,
            "zero_day_rumor": zero_day_rumor,
            "fact_contradiction": fact_contradiction,
            "fact_contradiction_note": fact_contradiction_note,
        }

    @staticmethod
    def _contradicts_free_claim(raw_text: str, best_match: dict | None) -> bool:
        """True jika entri terdekat bicara soal layanan tanpa biaya, tetapi teks meminta uang/biaya."""
        if not best_match:
            return False
        entry_text = f"{best_match.get('claim', '')} {best_match.get('fact', '')}"
        if not FREE_SERVICE_RE.search(entry_text):
            return False
        for clause in CLAUSE_SPLIT_RE.split(raw_text):
            if FEE_CUE_RE.search(clause) and not NEGATION_RE.search(clause):
                return True
        return False

    def _determine_threat_domain(
        self,
        text: str,
        linguistic_data: dict,
        best_match: dict | None,
        scaled_score: float | None = None,
    ) -> str:
        text_lower = text.lower()

        if best_match and best_match.get("threat_category"):
            return best_match["threat_category"]

        if scaled_score is not None and scaled_score < 25.0:
            return "Informasi Umum"

        if any(w in text_lower for w in ["tni", "militer", "bintara", "panglima", "alutsista", "kodam", "babinsa"]):
            if scaled_score is not None and scaled_score < 45.0:
                return "Isu Pertahanan (Belum Terverifikasi)"
            return "Disinformasi Pertahanan"
        if linguistic_data.get("sara_triggers") or any(w in text_lower for w in ["agama", "suku", "pribumi", "etnis"]):
            return "Polarisasi SARA & Ketertiban"
        if any(w in text_lower for w in ["apk", "hadiah", "rekening", "transfer", "phising", "dana bantuan"]):
            return "Penipuan Siber & Scam"

        if scaled_score is not None and scaled_score < 45.0:
            return "Isu Publik (Belum Terverifikasi)"
        return "Manipulasi Isu Publik"