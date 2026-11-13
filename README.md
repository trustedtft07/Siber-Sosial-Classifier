# Siber Sosial - Verifikasi & Klasifikasi Konten

Aplikasi verifikasi dan klasifikasi disinformasi media sosial yang dikembangkan untuk Cyber Hackathon. Sistem memeriksa narasi teks maupun tautan rujukan guna mendeteksi indikasi hoaks, penipuan digital, dan manipulasi informasi publik.

---

## 1. Pendekatan Arsitektur

Sistem menggunakan alur verifikasi hibrida tiga lapis yang menggabungkan analisis gaya bahasa, pencocokan arsip fakta, dan pemeriksaan reputasi sumber:

1. **Layer 1: Analisis Linguistik & Gaya Bahasa (Bobot 30%)**
   * Normalisasi slang serta leetspeak, lalu mendeteksi kata pemicu urgensi, pencatutan otoritas, konspirasi, klaim anonim, dan polarisasi SARA.
   * Mengukur rasio huruf kapital dan tanda baca berlebih untuk menilai indikasi sensasionalisme.
2. **Layer 2: Pencocokan Arsip Fakta / RAG TF-IDF (Bobot 45%)**
   * Pencocokan kemiripan hibrid (n-gram kata dan karakter dengan *cosine similarity*) terhadap basis data klarifikasi terindeks.
   * Membandingkan klaim input dengan arsip rujukan yang telah diverifikasi (*SALAH*, *MISLEADING*, atau *BENAR*) beserta deteksi kontradiksi biaya/fakta.
3. **Layer 3: Verifikasi Sumber & Tautan (Bobot 25%)**
   * Evaluasi reputasi domain sumber (Tier 1: `.go.id`/`.mil.id`/media terverifikasi, Tier 2: situs eksternal umum, Tier 3: domain tiruan/*typosquatting* atau TLD berisiko).
   * Deteksi pola pesan berantai (*forwarded broadcast*) tanpa sumber primer yang jelas.
4. **Penjelas Hasil (XAI) & Ringkasan**
   * Menyusun daftar faktor penentu skor, kategori isu, dan saran tindak lanjut, dengan opsi ringkasan dari Local LLM (Ollama).

---

## 2. Struktur Direktori Proyek

```
siber-sosial-classifier/
├── core/
│   ├── linguistic.py           # Analisis gaya bahasa dan leksikon provokasi
│   ├── rag_engine.py           # Pencarian bukti fakta TF-IDF hibrid & cosine similarity
│   ├── source_verifier.py      # Verifikasi domain, typosquatting, dan pesan berantai
│   ├── url_scraper.py          # Ekstraksi konten URL berita dengan proteksi SSRF
│   ├── risk_scorer.py          # Perhitungan skor risiko komposit (0-100)
│   └── xai_reasoner.py         # Penyusunan faktor penentu, ringkasan, dan tindak lanjut
├── data/
│   ├── fact_checks.json        # Arsip klaim dan klarifikasi terverifikasi
│   └── provocative_lexicon.json# Kamus frasa pemicu kepanikan dan manipulasi
├── web/
│   ├── static/                 # Aset CSS dan JS antarmuka web
│   └── templates/index.html    # Antarmuka web Siber Sosial
├── test_pipeline.py            # Skrip pengujian otomatis pipeline
├── main.py                     # Entrypoint REST API FastAPI & server web
├── Dockerfile                  # Konfigurasi container
└── docker-compose.yml          # Konfigurasi deployment Docker
```

---

## 3. Cara Menjalankan Secara Lokal

### Prasyarat
* Python 3.11 atau lebih baru
* Virtual environment (disarankan)

### Langkah Menjalankan
```bash
# 1. Masuk ke direktori proyek
cd siber-sosial-classifier

# 2. Pasang dependensi
pip install -r requirements.txt

# 3. Jalankan pengujian pipeline
python test_pipeline.py

# 4. Jalankan server web
python main.py
```
Buka aplikasi melalui browser di `http://localhost:8000`. Dokumentasi API tersedia di `http://localhost:8000/docs`.

---

## 4. Deployment Menggunakan Docker

```bash
docker compose up -d --build
```

Untuk menghentikan layanan:
```bash
docker compose down
```

---

## 5. Daftar Endpoint API

* `POST /api/analyze`: Menerima payload JSON `{"text": "...", "url": "..."}` dan mengembalikan skor risiko 3 lapis, bukti rujukan, serta ringkasan analisis.
* `POST /api/analyze/batch` & `POST /api/analyze/batch/upload`: Analisis massal daftar narasi/tautan atau unggahan berkas `.txt`/`.csv`.
* `GET /api/fact-checks` & `POST /api/fact-checks`: Mengambil daftar arsip klarifikasi atau menambahkan entri rujukan baru.
* `GET /api/stats`: Informasi status mesin dan distribusi kategori arsip fakta.
* `GET /api/health`: Pengecekan status kesiapan layanan (*healthcheck*).
