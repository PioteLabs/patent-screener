"""Local-only web UI for the patent screener. Run with `patent-screener serve`.

Reuses the same pipeline (pipeline.py) and HTML templates (templates/) as the
CLI and the file-based report, so the browser view and the saved report match.
"""
from __future__ import annotations

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from pipeline import run_pipeline
from report import TEMPLATES_DIR, THEME_VARS

app = FastAPI(title="patent-screener")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "web_index.html", {**THEME_VARS})


@app.post("/screen", response_class=HTMLResponse)
def screen(request: Request, idea_text: str = Form(...)) -> HTMLResponse:
    result = run_pipeline(idea_text)
    entries = sorted(result.entries, key=lambda e: e.overlap_score, reverse=True)
    return templates.TemplateResponse(
        request,
        "web_results.html",
        {
            "idea": result.idea,
            "entries": entries,
            "sources_searched": result.sources_searched,
            "skipped": result.skipped,
            "usage": result.usage.summary(),
            **THEME_VARS,
        },
    )
