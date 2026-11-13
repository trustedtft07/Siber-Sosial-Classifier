import csv
import io
import os
import re
import threading
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator

from core.linguistic import LinguisticAnalyzer
from core.rag_engine import FactCheckRAG
from core.risk_scorer import RiskScorer
from core.source_verifier import SourceVerifier
from core.url_scraper import URLScraper
from core.xai_reasoner import XAIReasoner

BASE_DIR = Path(__file__).resolve().parent

MAX_REQUEST_BODY_BYTES = 1 * 1024 * 1024  # 1 MB batas total payload HTTP
MAX_UPLOAD_BYTES = 512 * 1024             # 512 KB batas berkas upload batch
MAX_UPLOAD_ENTRIES = 100
MAX_TEXT_LENGTH = 15000
MAX_BATCH_TEXT_LENGTH = 10000
MAX_URL_LENGTH = 2048

ALLOWED_UPLOAD_EXTENSIONS = {"txt", "csv"}
ALLOWED_UPLOAD_MIMES = {
    "",
    "text/plain",
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
}
BLOCKED_DOUBLE_EXTENSIONS = {
    "exe", "dll", "bat", "cmd", "sh", "ps1", "php", "phtml", "phar",
    "py", "rb", "pl", "js", "mjs", "ts", "html", "htm", "svg", "jar",
    "vbs", "scr", "com", "jsp", "asp", "aspx", "cgi", "hta", "msi",
    "zip", "rar", "7z", "gz", "tar", "pdf",
}
BINARY_MAGIC_SIGNATURES = (
    b"MZ",
    b"\x7fELF",
    b"\xca\xfe\xba\xbe",
    b"\xfe\xed\xfa\xce",
    b"\xfe\xed\xfa\xcf",
    b"%PDF-",
    b"PK\x03\x04",
    b"PK\x05\x06",
    b"Rar!",
    b"\x1f\x8b",
    b"BZh",
    b"7z\xbc\xaf",
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"GIF87a",
    b"GIF89a",
    b"RIFF",
    b"#!",
)

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
HTML_SHELL_RE = re.compile(r"<\s*(?:!doctype|html|script|svg|iframe|object|embed|\?php)\b", re.IGNORECASE)
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,40}$")
BINARY_CTRL_BYTES = frozenset(range(0x00, 0x09)) | {0x0B, 0x0C} | frozenset(range(0x0E, 0x20))

CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'; "
    "form-action 'self'"
)


class _PayloadTooLarge(Exception):
    pass


class RequestSizeLimitMiddleware:
    """Menolak payload melebihi batas byte baik via Content-Length maupun chunked stream."""

    def __init__(self, app_asgi, max_bytes: int = MAX_REQUEST_BODY_BYTES):
        self.app = app_asgi
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    content_length = int(value.decode("ascii"))
                except ValueError:
                    resp = JSONResponse({"detail": "Header Content-Length tidak valid."}, status_code=400)
                    await resp(scope, receive, send)
                    return
                if content_length < 0 or content_length > self.max_bytes:
                    resp = JSONResponse({"detail": "Ukuran permintaan melebihi batas maksimal 1 MB."}, status_code=413)
                    await resp(scope, receive, send)
                    return

        received = 0
        response_started = False

        async def guarded_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _PayloadTooLarge()
            return message

        async def tracked_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, guarded_receive, tracked_send)
        except _PayloadTooLarge:
            if not response_started:
                resp = JSONResponse({"detail": "Ukuran permintaan melebihi batas maksimal 1 MB."}, status_code=413)
                await resp(scope, receive, send)


class SlidingWindowRateLimiter:
    def __init__(self, limits: dict[tuple[str, str], tuple[int, int]]):
        self.limits = limits
        self._hits: dict[tuple[str, str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, method: str, path: str) -> int | None:
        rule = self.limits.get((method, path))
        if not rule:
            return None

        max_calls, window_sec = rule
        now = time.monotonic()
        bucket_key = (key, method, path)

        with self._lock:
            q = self._hits[bucket_key]
            cutoff = now - window_sec
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= max_calls:
                retry_after = max(1, int(window_sec - (now - q[0])))
                return retry_after
            q.append(now)
        return None


rate_limiter = SlidingWindowRateLimiter({
    ("POST", "/api/analyze"): (60, 60),
    ("POST", "/api/analyze/batch"): (30, 60),
    ("POST", "/api/analyze/batch/upload"): (15, 60),
    ("POST", "/api/fact-checks"): (15, 60),
})


def _sanitize_text(value: str | None) -> str | None:
    if value is None:
        return None
    if "\x00" in value:
        raise ValueError("Input mengandung byte nol yang tidak diizinkan.")
    cleaned = CONTROL_CHARS_RE.sub("", value)
    return cleaned.strip()


def _extract_client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    # Hanya percaya header Cloudflare jika koneksi langsung berasal dari loopback/reverse proxy lokal.
    if peer in {"127.0.0.1", "::1"} or peer.startswith(("10.", "172.", "192.168.")):
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip:
            return cf_ip.strip()[:64]
    return peer


app = FastAPI(
    title="Siber Sosial - Verifikasi Konten & Disinformasi",
    description="Engine verifikasi konten dan disinformasi media sosial berbasis model hibrida 3 lapisan.",
    version="1.1.0",
)

ASSET_VERSION = str(int(time.time()))

allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "").strip()
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.add_middleware(RequestSizeLimitMiddleware, max_bytes=MAX_REQUEST_BODY_BYTES)


@app.middleware("http")
async def security_and_cache_middleware(request: Request, call_next):
    retry_after = rate_limiter.check(_extract_client_ip(request), request.method, request.url.path)
    if retry_after is not None:
        return JSONResponse(
            status_code=429,
            content={"detail": "Terlalu banyak permintaan. Coba beberapa saat lagi."},
            headers={"Retry-After": str(retry_after)},
        )

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-XSS-Protection"] = "0"

    if request.url.path not in {"/docs", "/redoc"}:
        response.headers["Content-Security-Policy"] = CSP_POLICY

    forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
    if request.url.scheme == "https" or forwarded_proto == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
    elif request.url.path == "/":
        response.headers["Cache-Control"] = "no-store"

    return response


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

linguistic_analyzer = LinguisticAnalyzer()
rag_engine = FactCheckRAG()
source_verifier = SourceVerifier()
risk_scorer = RiskScorer()
xai_reasoner = XAIReasoner()
url_scraper = URLScraper()


class AnalyzeRequest(BaseModel):
    text: str | None = Field(default=None, max_length=MAX_TEXT_LENGTH, description="Teks narasi atau pesan")
    url: str | None = Field(default=None, max_length=MAX_URL_LENGTH, description="Tautan rujukan (opsional)")

    @field_validator("text", "url", mode="before")
    @classmethod
    def sanitize_fields(cls, v: str | None) -> str | None:
        return _sanitize_text(v)


class BatchItem(BaseModel):
    text: str | None = Field(default=None, max_length=MAX_BATCH_TEXT_LENGTH, description="Teks narasi")
    url: str | None = Field(default=None, max_length=MAX_URL_LENGTH, description="Tautan rujukan")

    @field_validator("text", "url", mode="before")
    @classmethod
    def sanitize_fields(cls, v: str | None) -> str | None:
        return _sanitize_text(v)


class BatchAnalyzeRequest(BaseModel):
    items: list[BatchItem] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Daftar item untuk diproses sekaligus (maksimal 20 item)",
    )


class FactCheckCreateRequest(BaseModel):
    claim: str = Field(..., min_length=5, max_length=1000, description="Klaim atau narasi")
    fact: str = Field(..., min_length=5, max_length=2000, description="Penjelasan fakta atau klarifikasi")
    verdict: str = Field(..., max_length=20, description="Status: SALAH, MISLEADING, atau BENAR")
    threat_category: str = Field(..., min_length=2, max_length=100, description="Kategori konten")
    source_agency: str = Field(..., min_length=2, max_length=120, description="Lembaga penerbit klarifikasi")
    reference_url: str = Field(..., min_length=10, max_length=1024, description="Tautan rujukan")
    date: str | None = Field(default=None, max_length=10, description="Tanggal publikasi (YYYY-MM-DD)")
    id: str | None = Field(default=None, max_length=40, description="ID entri (opsional)")

    @field_validator("claim", "fact", "verdict", "threat_category", "source_agency", "reference_url", "date", "id", mode="before")
    @classmethod
    def sanitize_fields(cls, v: str | None) -> str | None:
        return _sanitize_text(v)

    @field_validator("reference_url")
    @classmethod
    def validate_reference_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("reference_url harus berupa URL HTTP/HTTPS yang valid tanpa kredensial.")
        return v

    @field_validator("id")
    @classmethod
    def validate_id_format(cls, v: str | None) -> str | None:
        if v and not SAFE_ID_RE.match(v):
            raise ValueError("ID hanya boleh berisi huruf, angka, tanda hubung, atau garis bawah (3-40 karakter).")
        return v

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: str | None) -> str | None:
        if v:
            datetime.strptime(v, "%Y-%m-%d")
        return v


def _execute_analysis(text: str, url: str | None, scraped_metadata: dict | None) -> dict:
    linguistic_result = linguistic_analyzer.analyze(text)
    evidence_matches = rag_engine.search_evidence(text, top_k=3)
    source_result = source_verifier.verify(text, explicit_url=url)

    risk_result = risk_scorer.calculate(
        linguistic_data=linguistic_result,
        evidence_data=evidence_matches,
        source_data=source_result,
        raw_text=text,
    )

    explanation = xai_reasoner.generate_explanation(
        analysis_result=risk_result,
        raw_text=text,
        linguistic_data=linguistic_result,
        evidence_list=evidence_matches,
        source_data=source_result,
        scraped_metadata=scraped_metadata,
    )

    return {
        "status": "success",
        "input_preview": text[:150] + ("..." if len(text) > 150 else ""),
        "scraped_metadata": scraped_metadata,
        "risk_assessment": risk_result,
        "layers": {
            "linguistic": linguistic_result,
            "evidence": evidence_matches,
            "source": source_result,
        },
        "explainable_ai": explanation,
    }


def _validate_and_parse_upload(filename: str, content_type: str, raw_bytes: bytes) -> tuple[str, list[str]]:
    if not filename or any(ch in filename for ch in ("/", "\\", "\x00")) or ".." in filename or len(filename) > 150:
        raise HTTPException(status_code=400, detail="Nama berkas tidak valid.")

    safe_name = PurePosixPath(filename).name
    parts = safe_name.lower().split(".")
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Ekstensi berkas wajib .txt atau .csv.")

    ext = parts[-1]
    if ext not in ALLOWED_UPLOAD_EXTENSIONS or (set(parts[1:-1]) & BLOCKED_DOUBLE_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Format berkas tidak diizinkan. Hanya gunakan berkas .txt atau .csv.")

    mime = (content_type or "").split(";")[0].strip().lower()
    if mime not in ALLOWED_UPLOAD_MIMES:
        raise HTTPException(status_code=400, detail="Tipe MIME berkas tidak didukung.")

    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Berkas kosong.")

    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Ukuran berkas melebihi batas maksimal 512 KB.")

    for sig in BINARY_MAGIC_SIGNATURES:
        if raw_bytes.startswith(sig):
            raise HTTPException(status_code=400, detail="Berkas biner atau eksekutabel ditolak.")

    if any(b in BINARY_CTRL_BYTES for b in raw_bytes):
        raise HTTPException(status_code=400, detail="Berkas mengandung karakter kontrol atau biner yang tidak valid.")

    try:
        decoded = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Berkas harus berformat teks UTF-8 yang valid.") from exc

    if HTML_SHELL_RE.search(decoded):
        raise HTTPException(status_code=400, detail="Berkas mengandung tag HTML atau skrip aktif yang tidak diizinkan.")

    entries: list[str] = []
    if ext == "csv":
        try:
            reader = csv.reader(io.StringIO(decoded))
            for row in reader:
                joined = " ".join(cell.strip() for cell in row if cell and cell.strip())
                if len(joined) > 5:
                    entries.append(joined[:MAX_BATCH_TEXT_LENGTH])
        except csv.Error as exc:
            raise HTTPException(status_code=400, detail="Format CSV tidak valid.") from exc
    else:
        splitter = r"\r?\n\s*\r?\n" if re.search(r"\r?\n\s*\r?\n", decoded) else r"\r?\n"
        for chunk in re.split(splitter, decoded):
            cleaned = chunk.strip()
            if len(cleaned) > 5:
                entries.append(cleaned[:MAX_BATCH_TEXT_LENGTH])

    if not entries:
        raise HTTPException(status_code=400, detail="Tidak ada teks yang memenuhi syarat minimal 6 karakter.")

    if len(entries) > MAX_UPLOAD_ENTRIES:
        raise HTTPException(
            status_code=400,
            detail=f"Jumlah baris melebihi batas maksimal {MAX_UPLOAD_ENTRIES} entri per berkas.",
        )

    return safe_name, entries


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"asset_version": ASSET_VERSION},
    )


@app.post("/api/analyze")
def analyze_content(payload: AnalyzeRequest):
    raw_text = payload.text.strip() if payload.text else ""
    raw_url = payload.url.strip() if payload.url else None

    if not raw_text and not raw_url:
        raise HTTPException(
            status_code=400,
            detail="Minimal sertakan teks narasi atau tautan URL berita untuk dianalisis.",
        )

    scraped_meta = None
    if raw_url:
        try:
            scraped = url_scraper.scrape(raw_url)
            scraped_meta = {
                "source_url": scraped["source_url"],
                "title": scraped["title"],
                "word_count": scraped["word_count"],
            }
            if not raw_text:
                raw_text = scraped["text"]
        except ValueError as exc:
            if not raw_text:
                raise HTTPException(status_code=400, detail=f"Gagal mengambil artikel: {exc}")
            scraped_meta = {"source_url": raw_url, "error": str(exc)}
        except Exception:
            if not raw_text:
                raise HTTPException(status_code=502, detail="Gagal mengakses tautan berita.")
            scraped_meta = {"source_url": raw_url, "error": "Gagal mengakses tautan sumber."}

    if not raw_text or len(raw_text) < 3:
        raise HTTPException(status_code=400, detail="Konten teks tidak memadai untuk dianalisis.")

    raw_text = raw_text[:MAX_TEXT_LENGTH]
    return _execute_analysis(raw_text, raw_url, scraped_meta)


@app.post("/api/analyze/batch/upload")
async def upload_batch_file(file: UploadFile = File(...)):
    chunks: list[bytes] = []
    total = 0
    try:
        while True:
            chunk = await file.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Ukuran berkas melebihi batas maksimal 512 KB.")
            chunks.append(chunk)
    finally:
        await file.close()

    safe_name, entries = _validate_and_parse_upload(
        filename=file.filename or "",
        content_type=file.content_type or "",
        raw_bytes=b"".join(chunks),
    )

    return {
        "status": "success",
        "filename": safe_name,
        "entry_count": len(entries),
        "text": "\n\n".join(entries),
    }


@app.post("/api/analyze/batch")
def analyze_batch(payload: BatchAnalyzeRequest):
    results = []
    threat_counts = {"KRITIS": 0, "TINGGI": 0, "SEDANG": 0, "RENDAH": 0}
    classification_counts = {
        "HOAX / DISINFORMASI": 0,
        "MISLEADING / PROVOKATIF": 0,
        "PERLU VERIFIKASI (BELUM TERBUKTI)": 0,
        "VALID / TERKONFIRMASI": 0,
    }

    for idx, item in enumerate(payload.items):
        item_text = item.text.strip() if item.text else ""
        item_url = item.url.strip() if item.url else None

        if not item_text and not item_url:
            results.append({
                "item_index": idx,
                "status": "error",
                "message": "Item kosong (tidak ada teks maupun URL).",
            })
            continue

        scraped_meta = None
        if item_url:
            try:
                scraped = url_scraper.scrape(item_url)
                scraped_meta = {
                    "source_url": scraped["source_url"],
                    "title": scraped["title"],
                    "word_count": scraped["word_count"],
                }
                if not item_text:
                    item_text = scraped["text"]
            except ValueError as exc:
                if not item_text:
                    results.append({
                        "item_index": idx,
                        "status": "error",
                        "message": f"Gagal mengekstrak URL: {exc}",
                    })
                    continue
                scraped_meta = {"source_url": item_url, "error": str(exc)}
            except Exception:
                if not item_text:
                    results.append({
                        "item_index": idx,
                        "status": "error",
                        "message": "Gagal mengakses tautan URL.",
                    })
                    continue
                scraped_meta = {"source_url": item_url, "error": "Gagal mengakses tautan sumber."}

        if not item_text or len(item_text) < 3:
            results.append({
                "item_index": idx,
                "status": "error",
                "message": "Konten teks kurang dari 3 karakter.",
            })
            continue

        item_text = item_text[:MAX_BATCH_TEXT_LENGTH]
        item_result = _execute_analysis(item_text, item_url, scraped_meta)
        item_result["item_index"] = idx

        threat = item_result["risk_assessment"].get("threat_level", "RENDAH")
        threat_counts[threat] = threat_counts.get(threat, 0) + 1

        cls_name = item_result["risk_assessment"].get("classification", "PERLU VERIFIKASI (BELUM TERBUKTI)")
        classification_counts[cls_name] = classification_counts.get(cls_name, 0) + 1

        results.append(item_result)

    return {
        "status": "success",
        "summary": {
            "total_items": len(payload.items),
            "successfully_analyzed": sum(threat_counts.values()),
            "threat_distribution": threat_counts,
            "classification_distribution": classification_counts,
        },
        "results": results,
    }


@app.get("/api/fact-checks")
async def get_fact_checks():
    return {
        "total": len(rag_engine.fact_checks),
        "data": rag_engine.fact_checks,
    }


@app.post("/api/fact-checks")
def create_fact_check(payload: FactCheckCreateRequest):
    verdict = payload.verdict.strip().upper()
    if verdict not in {"SALAH", "MISLEADING", "BENAR"}:
        raise HTTPException(status_code=400, detail="Verdict harus salah satu dari: SALAH, MISLEADING, atau BENAR.")

    category_slug = "".join(c for c in payload.threat_category if c.isalnum())[:3].upper()
    cat_code = category_slug or "GEN"
    generated_id = payload.id.strip() if payload.id else f"FC-{cat_code}-{len(rag_engine.fact_checks) + 1:03d}"

    if any(existing.get("id") == generated_id for existing in rag_engine.fact_checks):
        raise HTTPException(status_code=409, detail=f"ID entri '{generated_id}' sudah terdaftar.")

    entry_date = payload.date.strip() if payload.date else datetime.now().strftime("%Y-%m-%d")

    new_entry = {
        "id": generated_id,
        "claim": payload.claim.strip(),
        "fact": payload.fact.strip(),
        "verdict": verdict,
        "threat_category": payload.threat_category.strip(),
        "source_agency": payload.source_agency.strip(),
        "reference_url": payload.reference_url.strip(),
        "date": entry_date,
    }

    try:
        rag_engine.add_fact_check(new_entry, persist=True)
    except Exception:
        raise HTTPException(status_code=500, detail="Gagal menyimpan arsip ke penyimpanan.")

    return {
        "status": "success",
        "message": "Arsip klarifikasi berhasil ditambahkan.",
        "data": new_entry,
    }


@app.get("/api/stats")
async def get_system_stats():
    categories: dict[str, int] = {}
    for fc in rag_engine.fact_checks:
        cat = fc.get("threat_category", "Lainnya")
        categories[cat] = categories.get(cat, 0) + 1

    return {
        "engine_status": "ONLINE",
        "architecture": "3-Layer Hybrid Classifier",
        "knowledge_base_count": len(rag_engine.fact_checks),
        "categories_breakdown": categories,
        "local_llm_enabled": xai_reasoner.use_llm,
    }


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "siber-sosial-classifier"}


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host=host, port=port, reload=True)
