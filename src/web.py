"""Local-only web UI for the patent screener. Run with `patent-screener serve`.

A screening runs in a background thread so the browser can show live progress
instead of hanging on one long POST. Finished runs are saved to history.py's
sqlite store, so they survive a server restart; in-memory jobs (jobs.py) only
carry live progress for a run that is still going.
"""
from __future__ import annotations

import threading

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import history
from jobs import Job, create_job, get_job
from pipeline import run_pipeline
from report import TEMPLATES_DIR, THEME_VARS

app = FastAPI(title="patent-screener")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _run_in_background(job: Job) -> None:
    def worker() -> None:
        try:
            result = run_pipeline(job.idea_text, on_event=job.add_log, on_progress=job.set_progress)
            job.mark_done(result)
            history.save_run(
                job.id,
                result.idea,
                result.entries,
                result.sources_searched,
                result.skipped,
                result.usage.summary(),
            )
        except Exception as exc:  # noqa: BLE001 - surface any failure to the browser, don't crash the thread silently
            job.add_log(f"Error: {exc}")
            job.mark_error(str(exc))

    threading.Thread(target=worker, daemon=True).start()


def _nav_vars() -> dict:
    return {"today_spend": history.dashboard_stats()["cost_past_24_hours"]}


def _results_context(idea, entries, sources_searched, skipped, usage, run_id: str | None = None) -> dict:
    return {
        "idea": idea,
        "entries": sorted(entries, key=lambda e: e.overlap_score, reverse=True),
        "sources_searched": sources_searched,
        "skipped": skipped,
        "usage": usage,
        "run_id": run_id,
        **THEME_VARS,
        **_nav_vars(),
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    stats = history.dashboard_stats()
    recent_runs = history.list_runs(limit=5)
    return templates.TemplateResponse(
        request, "home.html", {"stats": stats, "recent_runs": recent_runs, **THEME_VARS, **_nav_vars()}
    )


@app.get("/new", response_class=HTMLResponse)
def new_screening(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "web_index.html", {**THEME_VARS, **_nav_vars()})


@app.post("/screen")
def screen(idea_text: str = Form(...)) -> RedirectResponse:
    job = create_job(idea_text)
    _run_in_background(job)
    return RedirectResponse(url=f"/runs/{job.id}", status_code=303)


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def view_run(request: Request, run_id: str) -> HTMLResponse:
    job = get_job(run_id)

    if job is None:
        record = history.get_run(run_id)
        if record is None:
            return templates.TemplateResponse(
                request, "not_found.html", {**THEME_VARS, **_nav_vars()}, status_code=404
            )
        return templates.TemplateResponse(
            request, "web_results.html", _results_context(**record, run_id=run_id)
        )

    if job.status == "running":
        return templates.TemplateResponse(request, "progress.html", {"job_id": job.id, **THEME_VARS})

    if job.status == "error":
        return templates.TemplateResponse(
            request, "error.html", {"error": job.error, "log": job.log, **THEME_VARS, **_nav_vars()}
        )

    result = job.result
    return templates.TemplateResponse(
        request,
        "web_results.html",
        _results_context(
            result.idea,
            result.entries,
            result.sources_searched,
            result.skipped,
            result.usage.summary(),
            run_id=job.id,
        ),
    )


@app.get("/runs/{run_id}/status")
def run_status(run_id: str) -> JSONResponse:
    job = get_job(run_id)
    if job is None:
        return JSONResponse({"status": "unknown"}, status_code=404)
    return JSONResponse(job.snapshot())


@app.get("/history", response_class=HTMLResponse)
def history_list(request: Request) -> HTMLResponse:
    runs = history.list_runs()
    return templates.TemplateResponse(request, "history.html", {"runs": runs, **THEME_VARS, **_nav_vars()})
