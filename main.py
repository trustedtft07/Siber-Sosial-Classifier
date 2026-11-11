import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from core.linguistic import LinguisticAnalyzer
from core.rag_engine import FactCheckRAG
from core.risk_scorer import RiskScorer
from core.source_verifier import SourceVerifier
from core.xai_reasoner import XAIReasoner

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Siber Sosial - Hoax & Disinformation Classifier",
    description="Engine verifikasi kognitif siber sosial berbasis 3-Layer Hybrid Model untuk PUSSIBERAD TNI AD.",
    version="1.0.0",
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


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=3, description="Teks narasi berita atau pesan berantai")
    url: str | None = Field(default=None, description="Tautan rujukan berita (opsional)")


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.post("/api/analyze")
async def analyze_content(payload: AnalyzeRequest):
    text = payload.text.strip()
    url = payload.url.strip() if payload.url else None

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
        "risk_assessment": risk_result,
        "layers": {
            "linguistic": linguistic_result,
            "evidence": evidence_matches,
            "source": source_result,
        },
        "explainable_ai": explanation,
    }


@app.get("/api/fact-checks")
async def get_fact_checks():
    return {
        "total": len(rag_engine.fact_checks),
        "data": rag_engine.fact_checks,
    }


@app.get("/api/stats")
async def get_system_stats():
    categories = {}
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
