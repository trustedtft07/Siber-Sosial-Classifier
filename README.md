# Sistem Klasifikasi Disinformasi Siber Sosial (Kategori 04: Cognitive Domain)

Purwarupa platform verifikasi dan deteksi disinformasi siber sosial yang dirancang untuk mendukung tugas pertahanan kognitif PUSSIBERAD TNI AD dalam mengidentifikasi narasi provokatif, hoaks pertahanan, dan manipulasi opini publik secara cepat dan terukur.

---

## 1. Pendekatan Arsitektur

Sistem menggunakan model verifikasi hibrida tiga lapis (Three-Layer Hybrid Verification) yang menggabungkan analisis linguistik teks, pencocokan bukti semantik (RAG), dan penilaian reputasi sumber:

1. **Layer 1: Linguistic & Stylometric Analyzer (Bobot 30%)**
   * Deteksi leksikon urgensi, pencatutan otoritas, konspirasi, dan polarisasi SARA.
   * Analisis pola huruf kapital (*ALL CAPS*) dan tanda baca berlebih untuk mengukur derajat sensasionalisme.
2. **Layer 2: Evidence Retrieval & Fact-Checking RAG (Bobot 45%)**
   * Pencocokan semantik klaim terhadap basis pengetahuan verifikasi terindeks (arsip TurnBackHoax Mafindo, klarifikasi Kemenkomdigi, dan rilis resmi Dispenad/Puspen TNI).
   * Menghitung derajat kemiripan klaim dengan arsip yang telah terverifikasi (*SALAH*, *MISLEADING*, atau *BENAR*).
3. **Layer 3: Source & Propagation Verifier (Bobot 25%)**
   * Evaluasi reputasi domain sumber (Tier 1: `.mil.id`/`.go.id`/media resmi, Tier 2: blog umum, Tier 3: domain berisiko/phishing).
   * Deteksi anomali pola pesan berantai (*chain broadcast* tanpa atribusi sumber primer).
4. **Explainable AI (XAI) & Taksonomi Ancaman**
   * Sintesis faktor risiko poin demi poin dan klasifikasi domain ancaman (*Disinformasi Pertahanan*, *Polarisasi SARA*, *Penipuan Siber*, atau *Manipulasi Isu Publik*).
   * Rekomendasi tindakan operasional untuk tim pemantau siber sosial.

---

## 2. Struktur Direktori Proyek

```
siber-sosial-classifier/
├── core/
│   ├── linguistic.py          # Analisis gaya bahasa dan leksikon provokasi
│   ├── rag_engine.py          # Retrieval-Augmented Generation & semantic search
│   ├── source_verifier.py     # Verifikasi domain dan heuristik pesan berantai
│   ├── risk_scorer.py         # Perhitungan skor risiko komposit (0-100)
│   └── xai_reasoner.py        # Sintesis penjelasan dan rekomendasi taktis
├── data/
│   ├── fact_checks.json       # Pangkalan data arsip klarifikasi terverifikasi
│   └── provocative_lexicon.json# Kamus leksikon pemicu kepanikan dan manipulasi
├── web/
│   ├── static/                # Aset CSS dan JS dashboard taktis
│   └── templates/index.html   # Antarmuka web Cognitive Operations Center
├── test_pipeline.py           # Skrip pengujian otomatis skenario kasus
├── main.py                    # Entrypoint REST API FastAPI & server web
├── Dockerfile                 # Konfigurasi container mandiri
└── docker-compose.yml         # Konfigurasi deployment sekali jalan
```

---

## 3. Cara Menjalankan Aplikasi Secara Lokal

### Prasyarat
* Python 3.11 atau lebih baru
* Virtual environment (opsional namun disarankan)

### Langkah Instalasi
```bash
# 1. Masuk ke direktori proyek
cd siber-sosial-classifier

# 2. Pasang dependensi
pip install -r requirements.txt

# 3. Jalankan pengujian skenario
python test_pipeline.py

# 4. Jalankan server dashboard
python main.py
```
Akses dashboard operasional melalui browser di `http://localhost:8000`. Dokumentasi interaktif Swagger API tersedia di `http://localhost:8000/docs`.

---

## 4. Deployment Menggunakan Docker

Sistem dapat dijalankan langsung di server fisik atau home-server menggunakan Docker:

```bash
docker compose up -d --build
```

Untuk menghentikan:
```bash
docker compose down
```

---

## 5. Spesifikasi Endpoint API

* `POST /api/analyze`: Menerima JSON payload `{"text": "...", "url": "..."}` dan menghasilkan analisis risiko 3 layer, rincian bukti rujukan, serta rekomendasi penanganan.
* `GET /api/fact-checks`: Menampilkan daftar arsip fakta yang tersimpan di basis pengetahuan lokal.
* `GET /api/stats`: Informasi status mesin dan ringkasan distribusi kategori ancaman.
* `GET /api/health`: Endpoint pengecekan status kesiapan layanan (*healthcheck*).
