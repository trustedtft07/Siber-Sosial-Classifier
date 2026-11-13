import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from core.linguistic import LinguisticAnalyzer
from core.rag_engine import FactCheckRAG
from core.risk_scorer import RiskScorer
from core.source_verifier import SourceVerifier
from core.url_scraper import URLScraper
from core.xai_reasoner import XAIReasoner

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Siber Sosial - Hoax & Disinformation Classifier",
    description="Engine verifikasi kognitif siber sosial berbasis 3-Layer Hybrid Model untuk PUSSIBERAD TNI AD.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "web" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "web" / "templates"))

linguistic_analyzer = LinguisticAnalyzer()
rag_engine = FactCheckRAG()
source_verifier = SourceVerifier()
risk_scorer = RiskScorer()
xai_reasoner = XAIReasoner()
url_scraper = URLScraper()


class AnalyzeRequest(BaseModel):
    text: str | None = Field(default=None, description="Teks narasi berita atau pesan berantai")
    url: str | None = Field(default=None, description="Tautan rujukan berita (opsional)")


class BatchItem(BaseModel):
    text: str | None = Field(default=None, description="Teks narasi")
    url: str | None = Field(default=None, description="Tautan rujukan berita")


class BatchAnalyzeRequest(BaseModel):
    items: list[BatchItem] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Daftar item untuk dianalisis sekaligus (maksimal 20 item)",
    )


class FactCheckCreateRequest(BaseModel):
    claim: str = Field(..., min_length=5, description="Pernyataan atau klaim hoaks/berita")
    fact: str = Field(..., min_length=5, description="Penjelasan fakta sebenarnya atau sanggahan")
    verdict: str = Field(..., description="Vonis klarifikasi: SALAH, MISLEADING, atau BENAR")
    threat_category: str = Field(..., description="Kategori ancaman siber sosial")
    source_agency: str = Field(..., description="Instansi penerbit klarifikasi resmi")
    reference_url: str = Field(..., description="Tautan rujukan resmi verifikasi")
    date: str | None = Field(default=None, description="Tanggal publikasi klarifikasi (YYYY-MM-DD)")
    id: str | None = Field(default=None, description="ID arsip (opsional, auto-generated jika kosong)")


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


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


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
        except Exception as exc:
            if not raw_text:
                raise HTTPException(status_code=502, detail=f"Gagal mengakses tautan berita: {exc}")
            scraped_meta = {"source_url": raw_url, "error": str(exc)}

    if not raw_text or len(raw_text) < 3:
        raise HTTPException(status_code=400, detail="Konten teks tidak memadai untuk dianalisis.")

    return _execute_analysis(raw_text, raw_url, scraped_meta)


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
            except Exception as exc:
                if not item_text:
                    results.append({
                        "item_index": idx,
                        "status": "error",
                        "message": f"Gagal mengekstrak URL: {exc}",
                    })
                    continue
                scraped_meta = {"source_url": item_url, "error": str(exc)}

        if not item_text or len(item_text) < 3:
            results.append({
                "item_index": idx,
                "status": "error",
                "message": "Konten teks kurang dari 3 karakter.",
            })
            continue

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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan arsip ke disk: {exc}")

    return {
        "status": "success",
        "message": "Arsip klarifikasi berhasil ditambahkan dan model RAG telah diperbarui.",
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
        "architecture": "3-Layer Hybrid Cognitive Defense",
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
