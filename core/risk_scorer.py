class RiskScorer:
    WEIGHT_LINGUISTIC = 0.30
    WEIGHT_EVIDENCE = 0.45
    WEIGHT_SOURCE = 0.25

    ZERO_DAY_MAX_SIMILARITY = 0.25
    ZERO_DAY_MIN_RISK = 0.70
    ZERO_DAY_FLOOR = 0.45  # = batas bawah status MISLEADING / PROVOKATIF

    def calculate(self, linguistic_data: dict, evidence_data: list[dict], source_data: dict, raw_text: str) -> dict:
        linguistic_score = linguistic_data.get("linguistic_score", 0.0)
        source_risk = source_data.get("source_risk", 0.40)

        best_match = evidence_data[0] if evidence_data else None
        sim_score = best_match.get("similarity_score", 0.0) if best_match else 0.0
        verdict = best_match.get("verdict", "TIDAK_DIKETAHUI") if best_match else "TIDAK_DIKETAHUI"

        if sim_score >= 0.30:
            if verdict == "SALAH":
                evidence_risk = min(1.0, 0.70 + (sim_score * 0.30))
            elif verdict == "MISLEADING":
                evidence_risk = min(1.0, 0.50 + (sim_score * 0.35))
            elif verdict == "BENAR":
                evidence_risk = max(0.02, 0.15 - (sim_score * 0.15))
            else:
                evidence_risk = 0.45
        else:
            evidence_risk = 0.35

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
            action_code = "AWAITING_FURTHER_INTEL"
        else:
            classification = "VALID / TERKONFIRMASI"
            threat_level = "RENDAH"
            action_code = "CLEAR_STATUS"

        threat_domain = self._determine_threat_domain(raw_text, linguistic_data, best_match)

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
            "best_match": best_match if sim_score >= 0.25 else None,
            "zero_day_rumor": zero_day_rumor,
        }

    def _determine_threat_domain(self, text: str, linguistic_data: dict, best_match: dict | None) -> str:
        text_lower = text.lower()

        if best_match and best_match.get("threat_category"):
            return best_match["threat_category"]

        if any(w in text_lower for w in ["tni", "militer", "bintara", "panglima", "alutsista", "kodam", "babinsa"]):
            return "Disinformasi Pertahanan"
        if linguistic_data.get("sara_triggers") or any(w in text_lower for w in ["agama", "suku", "pribumi", "etnis"]):
            return "Polarisasi SARA & Ketertiban"
        if any(w in text_lower for w in ["apk", "hadiah", "rekening", "transfer", "phising", "dana bantuan"]):
            return "Penipuan Siber & Scam"

        return "Manipulasi Isu Publik"