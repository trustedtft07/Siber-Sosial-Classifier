import json
import os
import tempfile
import threading
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class FactCheckRAG:
    """Pencari bukti klarifikasi (Layer 2).

    Kemiripan = 70% kemiripan KATA (n-gram 1-3) + 30% kemiripan KARAKTER (char_wb n-gram 3-5).
    Kemiripan karakter membuat pencarian tetap tahan terhadap typo / huruf diganti angka
    ("pener1maan b1ntara") yang sengaja dipakai penyebar hoaks.
    """

    WORD_WEIGHT = 0.70
    CHAR_WEIGHT = 0.30

    def __init__(self, data_path: Path | None = None):
        if data_path is None:
            data_path = Path(__file__).resolve().parent.parent / "data" / "fact_checks.json"

        self.data_path = Path(data_path)
        self._lock = threading.Lock()  # API bisa dipanggil bersamaan (tambah data vs. pencarian)

        with open(self.data_path, "r", encoding="utf-8") as f:
            self.fact_checks = json.load(f)

        self._build_index()

    # ------------------------------------------------------------------ #
    def _build_index(self) -> None:
        """(Re)bangun vektor TF-IDF dari seluruh klaim. Dipanggil saat awal & setelah data bertambah."""
        self.claims = [item["claim"] for item in self.fact_checks]

        self.word_vectorizer = TfidfVectorizer(
            ngram_range=(1, 3), analyzer="word", sublinear_tf=True, min_df=1
        )
        self.char_vectorizer = TfidfVectorizer(
            ngram_range=(3, 5), analyzer="char_wb", sublinear_tf=True, min_df=1
        )

        if self.claims:
            self.word_vectors = self.word_vectorizer.fit_transform(self.claims)
            self.char_vectors = self.char_vectorizer.fit_transform(self.claims)
        else:
            self.word_vectors = None
            self.char_vectors = None

        # Nama lama dipertahankan supaya kode lain yang mungkin merujuknya tidak rusak.
        self.vectorizer = self.word_vectorizer
        self.claim_vectors = self.word_vectors

    # ------------------------------------------------------------------ #
    def search_evidence(self, query: str, top_k: int = 3) -> list[dict]:
        clean_query = query.strip()
        if not clean_query:
            return []

        with self._lock:
            if not self.claims:
                return []

            word_sim = cosine_similarity(
                self.word_vectorizer.transform([clean_query]), self.word_vectors
            ).flatten()
            char_sim = cosine_similarity(
                self.char_vectorizer.transform([clean_query]), self.char_vectors
            ).flatten()
            similarities = (self.WORD_WEIGHT * word_sim) + (self.CHAR_WEIGHT * char_sim)

            ranked_indices = similarities.argsort()[::-1][:top_k]
            results = []
            for idx in ranked_indices:
                item = dict(self.fact_checks[idx])
                item["similarity_score"] = round(float(similarities[idx]), 3)
                results.append(item)

        return results

    # ------------------------------------------------------------------ #
    def add_fact_check(self, entry: dict, persist: bool = False) -> None:
        """Tambah klarifikasi baru; langsung bisa dicari tanpa restart / training ulang.

        - Jika 'id' sudah ada, entri lama DIGANTI (bukan dobel), jadi aman dipanggil ulang.
        - persist=True sekaligus menyimpan ke file (sama dengan memanggil save_to_disk()).
        """
        if not entry.get("claim"):
            raise ValueError("entry harus punya field 'claim'")

        with self._lock:
            entry_id = entry.get("id")
            replaced = False
            if entry_id:
                for i, existing in enumerate(self.fact_checks):
                    if existing.get("id") == entry_id:
                        self.fact_checks[i] = entry
                        replaced = True
                        break
            if not replaced:
                self.fact_checks.append(entry)
            self._build_index()

        if persist:
            self.save_to_disk()

    # ------------------------------------------------------------------ #
    def save_to_disk(self, path: Path | None = None) -> None:
        """Simpan seluruh arsip ke JSON. Ditulis ke file sementara dulu lalu diganti,
        supaya file asli tidak rusak kalau proses terhenti di tengah penulisan."""
        target = Path(path) if path else self.data_path

        with self._lock:
            payload = json.dumps(self.fact_checks, ensure_ascii=False, indent=2)

        fd, tmp_name = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp_name, target)
        except Exception:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
            raise