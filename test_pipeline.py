from core.linguistic import LinguisticAnalyzer
from core.rag_engine import FactCheckRAG
from core.risk_scorer import RiskScorer
from core.source_verifier import SourceVerifier
from core.xai_reasoner import XAIReasoner


def test_samples():
    ling = LinguisticAnalyzer()
    rag = FactCheckRAG()
    src = SourceVerifier()
    scorer = RiskScorer()
    xai = XAIReasoner()

    samples = [
        (
            "Hoax Rekrutmen TNI",
            "Penerimaan Calon Bintara PK TNI AD 2026 membuka kuota jalur kilat dengan biaya administrasi via transfer rekening perorangan. Diteruskan berkali-kali! Sebarkan sebelum kuota habis!",
            "https://rekrutmen-tni-jalurkhusus.xyz/daftar",
        ),
        (
            "Kudeta Misleading",
            "VIRAL DARURAT! Beredar video pergerakan puluhan tank dan kendaraan taktis TNI AD menuju istana. Dikabarkan ada rencana kudeta militer dan pengambilalihan kekuasaan!",
            None,
        ),
        (
            "Berita Valid TNI",
            "Mabes TNI AD secara resmi memberangkatkan satgas kesehatan dan logistik Batalyon Kesehatan Divif untuk membantu evakuasi warga korban erupsi gunung berapi di wilayah timur.",
            "https://tniad.mil.id/tni-ad-terjunkan-satgas-bencana-erupsi",
        ),
    ]

    for title, text, url in samples:
        l_res = ling.analyze(text)
        e_res = rag.search_evidence(text, top_k=2)
        s_res = src.verify(text, explicit_url=url)
        r_res = scorer.calculate(l_res, e_res, s_res, text)
        x_res = xai.generate_explanation(r_res, text, l_res, e_res, s_res)

        print(f"[{title}]")
        print(f"Skor Risiko: {r_res['score']}/100 | Klasifikasi: {r_res['classification']}")
        print(f"Kategori Ancaman: {r_res['threat_domain']}")
        print(f"Ringkasan: {x_res['tactical_brief']}")
        print(f"Rekomendasi: {x_res['counter_measure']}")
        print("-" * 50)


if __name__ == "__main__":
    test_samples()
