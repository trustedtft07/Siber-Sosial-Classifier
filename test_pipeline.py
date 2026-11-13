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


# ----------------------------------------------------------------------------------------
# EVALUASI METRIK (Subtask 2.4)
# ----------------------------------------------------------------------------------------
# Kelas POSITIF  = hoaks  -> klasifikasi "HOAX / DISINFORMASI" atau "MISLEADING / PROVOKATIF".
# Kelas NEGATIF  = valid  -> "VALID / TERKONFIRMASI" atau "PERLU VERIFIKASI (BELUM TERBUKTI)".
# "PERLU VERIFIKASI" dihitung negatif: sistem sengaja tidak menuduh hoaks tanpa bukti (Zero-Day Rumor).
FLAGGED = {"HOAX / DISINFORMASI", "MISLEADING / PROVOKATIF"}

# (id, teks, url, is_hoax, asal)   asal: "DB" = isu mirip arsip yang ada, "BARU" = isu belum ada di database
EVAL_SAMPLES = [
    # ---- 10 HOAKS / MISLEADING -------------------------------------------------------------
    ("H01", "Info A1!! pener1maan b1ntara TNI AD 2026 jalur kilat, bayar adm via transfer rekening pribadi. Sebarkan ke semua grup!!!",
     "http://rekrutmen-tniad.net/daftar", True, "DB"),
    ("H02", "VIRAL! Video tank dan panser TNI AD bergerak ke Jakarta mau kudeta ambil alih kekuasaan. Media bungkam, sebarkan!",
     None, True, "DB"),
    ("H03", "Pencairan santunan veteran dan pensiunan TNI AD lewat link pendaftaran apk di telegram, buruan daftar sebelum ditutup",
     "https://santunan-veteran.top/apk", True, "DB"),
    ("H04", "Ada oknum yang bisa meloloskan anak jadi tamtama TNI AD 2026, cukup setor uang dulu, dijamin lulus",
     None, True, "DB"),
    ("H05", "Surat peringatan resmi Komdigi: internet seluruh Indonesia dimatikan 3 hari, segera tarik uang tunai di ATM! Sebarkan!!",
     None, True, "DB"),
    ("H06", "Undangan dari Panglima TNI, seluruh rakyat diminta kumpul di Monas hari Sabtu jam 7 pagi, harap disebarkan",
     None, True, "DB"),
    ("H07", "INFO A1 dari orang dalam: Panglima TNI akan umumkan darurat militer besok malam, semua warga dilarang keluar rumah. Media bungkam! SEBARKAN SEBELUM DIHAPUS!!!",
     "https://info-darurat-tni.xyz/berita", True, "BARU"),
    ("H08", "Kata orang dalam, pemerintah menyembunyikan data prajurit TNI yang gugur di perbatasan, kabar burung ini harus viral!",
     None, True, "BARU"),
    ("H09", "Pendaftaran jalur khusus Tamtama TNI AD 2027 dibuka, biaya administrasi 15 juta transfer ke rekening panitia, kuota terbatas",
     "http://tniad-mil.com/jalur-khusus", True, "BARU"),
    ("H10", "Kodam III/Siliwangi resmi dipindahkan ke Garut mulai 12 November 2026 atas keputusan Panglima TNI.",
     None, True, "BARU"),   # hoaks berbahasa baku tanpa penanda: batasan yang diakui di dokumen konteks
    # ---- 10 VALID --------------------------------------------------------------------------
    ("V01", "TNI AD memberangkatkan satgas kesehatan dan logistik untuk membantu evakuasi korban erupsi gunung api di wilayah timur.",
     "https://tniad.mil.id/berita/satgas-erupsi", False, "DB"),
    ("V02", "Kapal ADRI LII milik TNI AD berangkat dari Jakarta membawa logistik bencana untuk Medan dan Lhokseumawe.",
     "https://www.metrotvnews.com/read/berita-adri", False, "DB"),
    ("V03", "Pendaftaran Bintara PK TNI AD gelombang I 2026 dibuka 7 Januari sampai 6 Februari lewat situs resmi dan tidak dipungut biaya.",
     "https://ad.rekrutmen-tni.mil.id", False, "DB"),
    ("V04", "Kemhan menjelaskan pelibatan warga sipil dalam pertahanan bersifat sukarela lewat Komcad, tidak ada wajib militer.",
     None, False, "DB"),
    ("V05", "Dua ratus prajurit Satgas Yonif TP 837 Kodam Brawijaya diberangkatkan ke Aceh Utara untuk membantu pemulihan pascabencana.",
     None, False, "DB"),
    ("V06", "Kapuspen TNI menyampaikan TNI AD akan menggelar latihan gabungan di Baturaja pekan depan sesuai jadwal tahunan.",
     None, False, "BARU"),
    ("V07", "BMKG mengimbau masyarakat pesisir mewaspadai gelombang tinggi selama tiga hari ke depan.",
     "https://www.bmkg.go.id/cuaca", False, "BARU"),
    ("V08", "Kementerian Pendidikan membuka pendaftaran beasiswa untuk mahasiswa S2 dalam negeri tahun 2027.",
     "https://kemdikbud.go.id/beasiswa", False, "BARU"),
    ("V09", "Presiden meresmikan ruas tol baru dan meminta pengelola menjaga kualitas jalan serta pelayanan pengguna.",
     None, False, "BARU"),
    ("V10", "Pemerintah daerah menyalurkan bantuan pangan murah kepada warga di sejumlah kecamatan pekan ini.",
     "https://www.antaranews.com/berita/pangan-murah", False, "BARU"),
]


def _prf(tp: int, fp: int, fn: int, tn: int) -> dict:
    total = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "accuracy": (tp + tn) / total if total else 0.0,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def evaluate_metrics(verbose: bool = True) -> dict:
    """Uji 20 sampel (10 hoaks, 10 valid) lewat pipeline 3-layer lalu hitung Accuracy, Precision, Recall, F1."""
    ling, rag, src, scorer = LinguisticAnalyzer(), FactCheckRAG(), SourceVerifier(), RiskScorer()

    rows = []
    for sid, text, url, is_hoax, origin in EVAL_SAMPLES:
        l_res = ling.analyze(text)
        e_res = rag.search_evidence(text, top_k=2)
        s_res = src.verify(text, explicit_url=url)
        r_res = scorer.calculate(l_res, e_res, s_res, text)
        predicted = r_res["classification"] in FLAGGED
        rows.append((sid, origin, is_hoax, predicted, r_res["score"], r_res["classification"]))

    tp = sum(1 for _, _, y, p, _, _ in rows if y and p)
    fn = sum(1 for _, _, y, p, _, _ in rows if y and not p)
    fp = sum(1 for _, _, y, p, _, _ in rows if not y and p)
    tn = sum(1 for _, _, y, p, _, _ in rows if not y and not p)
    overall = _prf(tp, fp, fn, tn)

    def subset(origin):
        r = [x for x in rows if x[1] == origin]
        return _prf(
            sum(1 for _, _, y, p, _, _ in r if y and p), sum(1 for _, _, y, p, _, _ in r if not y and p),
            sum(1 for _, _, y, p, _, _ in r if y and not p), sum(1 for _, _, y, p, _, _ in r if not y and not p),
        )

    if verbose:
        print("=" * 78)
        print("EVALUASI METRIK - 20 sampel (10 hoaks/misleading, 10 valid)")
        print("Positif = HOAX / DISINFORMASI atau MISLEADING / PROVOKATIF")
        print("=" * 78)
        print(f"{'ID':4} {'Asal':5} {'Label':7} {'Prediksi':9} {'Skor':>6}  Klasifikasi")
        for sid, origin, y, p, score, cls in rows:
            mark = "" if y == p else "   <-- SALAH"
            print(f"{sid:4} {origin:5} {'HOAKS' if y else 'VALID':7} {'HOAKS' if p else 'VALID':9} {score:6.1f}  {cls}{mark}")
        print("-" * 78)
        print(f"Confusion matrix:  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
        print(f"Accuracy : {overall['accuracy']*100:5.1f}%")
        print(f"Precision: {overall['precision']*100:5.1f}%")
        print(f"Recall   : {overall['recall']*100:5.1f}%")
        print(f"F1-Score : {overall['f1']*100:5.1f}%")
        for origin, label in (("DB", "isu MIRIP arsip database"), ("BARU", "isu BARU (belum ada di database)")):
            s = subset(origin)
            print(f"  - {label}: Accuracy {s['accuracy']*100:.0f}% | Recall {s['recall']*100:.0f}%")
        print("Catatan: 20 sampel buatan sendiri = indikator awal, bukan bukti akurasi di data nyata.")
        print("=" * 78)

    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, **overall}


if __name__ == "__main__":
    test_samples()
    evaluate_metrics()