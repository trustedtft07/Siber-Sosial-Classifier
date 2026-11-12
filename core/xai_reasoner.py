import os
import requests


class XAIReasoner:
    def __init__(self):
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
        self.use_llm = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
        self.timeout = int(os.getenv("OLLAMA_TIMEOUT", "4"))

    def generate_explanation(
        self,
        analysis_result: dict,
        raw_text: str,
        linguistic_data: dict,
        evidence_list: list[dict],
        source_data: dict,
    ) -> dict:
        reasons = []

        best_match = analysis_result.get("best_match")
        if best_match:
            sim = int(best_match["similarity_score"] * 100)
            reasons.append(
                f"Klaim memiliki kemiripan semantik {sim}% dengan arsip klarifikasi '{best_match['id']}' "
                f"({best_match['source_agency']}) berstatus {best_match['verdict']}."
            )
        else:
            reasons.append("Klaim belum terdata langsung di database klarifikasi; dianalisis sebagai isu berkembang.")

        triggers = []
        if linguistic_data.get("urgency_triggers"):
            triggers.append(f"urgensi/kepanikan ({', '.join(linguistic_data['urgency_triggers'])})")
        if linguistic_data.get("authority_triggers"):
            triggers.append(f"pencatutan otoritas ({', '.join(linguistic_data['authority_triggers'])})")
        if linguistic_data.get("conspiracy_triggers"):
            triggers.append(f"narasi konspirasi ({', '.join(linguistic_data['conspiracy_triggers'])})")
        if linguistic_data.get("sara_triggers"):
            triggers.append(f"polarisasi SARA ({', '.join(linguistic_data['sara_triggers'])})")
        if linguistic_data.get("anonymous_claim_triggers"):
            triggers.append(f"klaim anonim tanpa sumber rujukan ({', '.join(linguistic_data['anonymous_claim_triggers'])})")

        if triggers:
            reasons.append(f"Ditemukan indikator manipulasi bahasa: {'; '.join(triggers)}.")
        elif linguistic_data.get("caps_ratio", 0) > 0.3:
            reasons.append("Pola penulisan menggunakan dominasi huruf kapital (indikasi sensasionalisme).")
        else:
            reasons.append("Struktur kalimat relatif wajar tanpa leksikon provokatif eksplisit.")

        if source_data.get("is_chain_message"):
            reasons.append("Format teks teridentifikasi sebagai pesan berantai (forwarded/broadcast) tanpa rujukan primer.")
        elif source_data.get("source_tier") == "TIER_1_VERIFIED":
            reasons.append("Tautan merujuk pada domain kredibel (.mil.id, .go.id, atau media pers terverifikasi).")
        elif source_data.get("source_tier") == "TIER_3_SUSPICIOUS":
            reasons.append("Tautan menggunakan domain berisiko tinggi atau indikasi phishing/spoofing.")

        brief = self._generate_tactical_brief(analysis_result, reasons, raw_text)

        return {
            "key_factors": reasons,
            "tactical_brief": brief,
            "counter_measure": self._get_counter_measure(analysis_result["threat_level"]),
        }

    def _generate_tactical_brief(self, analysis: dict, reasons: list[str], raw_text: str) -> str:
        if self.use_llm:
            try:
                prompt = (
                    "Anda adalah analis intelijen siber PUSSIBERAD TNI AD.\n"
                    "Buat tepat 2 kalimat ringkasan taktis (tegas, formal, objektif, tanpa basa-basi) mengenai status konten berikut:\n"
                    f"- Narasi: \"{raw_text[:200]}\"\n"
                    f"- Tingkat Ancaman: {analysis['threat_level']} (Skor {analysis['score']}/100, Kategori {analysis['threat_domain']})\n"
                    f"- Faktor Temuan: {' '.join(reasons)}\n"
                    "Ringkasan Taktis:"
                )
                payload = {
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.2,
                        "num_predict": 120,
                    },
                }
                resp = requests.post(
                    f"{self.ollama_host}/api/generate",
                    json=payload,
                    timeout=self.timeout,
                )
                if resp.status_code == 200:
                    output = resp.json().get("response", "").strip()
                    if output:
                        return output
            except Exception:
                pass

        return (
            f"Konten teridentifikasi pada tingkat risiko {analysis['threat_level']} ({analysis['score']}/100) dalam kategori {analysis['threat_domain']}. "
            f"{reasons[0]}"
        )

    def _get_counter_measure(self, threat_level: str) -> str:
        if threat_level == "KRITIS":
            return "Rekomendasi Operasional: Terbitkan rilis sanggahan resmi melalui Dispenad/Puspen TNI, lakukan koordinasi blokir tautan dengan BSSN & Komdigi, dan pantau sebaran akun penyebar."
        if threat_level == "TINGGI":
            return "Rekomendasi Operasional: Laporkan ke tim pemantau isu siber sosial untuk menyiapkan kontra-narasi dan periksa mutasi postingan di grup publik."
        if threat_level == "SEDANG":
            return "Rekomendasi Operasional: Pantau sentimen dan kecepatan penyebaran; belum memerlukan penindakan aktif."
        return "Rekomendasi Operasional: Konten konsisten dengan fakta terverifikasi; tidak ada tindakan diperlukan."
