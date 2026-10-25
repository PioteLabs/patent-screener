# Patent Screener

A command-line tool that takes a plain-text product idea and screens it against existing patents. It outputs a ranked report of the closest patents, their legal status, and which claim elements overlap with the idea.

This is a **screening aid, not legal advice**. It does not render infringement opinions and should not replace a consultation with a patent attorney.

## What it does

1. **Extract** - breaks a plain-text idea into discrete elements (components, relationships, functions) and generates search terms.
2. **Search** - queries patent data sources with multiple query variants and deduplicates results.
3. **Fetch** - pulls independent claims and legal status for each candidate patent.
4. **Compare** - checks the idea against each claim element by element, flagging present, absent, or unclear elements.
5. **Report** - writes a ranked markdown report with a design-around suggestion for each close hit.

## Status

Early development. See issues/project board for current progress.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
cp .env.example .env
# fill in ANTHROPIC_API_KEY and USPTO_API_KEY
pip install -e .
```

## Usage

**Web UI (recommended):**

```bash
patent-screener serve
```

Open `http://127.0.0.1:8000`, paste your idea into the textarea, and submit. A
screening runs in the background; the page shows a live progress bar (extract
-> search -> compare -> finalize) with an expandable activity log, then lands
on a ranked list of matching patents with reference links and a token/cost
breakdown for the run. Past runs are saved and browsable from "History"; a
run's URL (`/runs/<id>`) is a permalink that still works after a server
restart. Local only - do not expose this to the internet, it has no auth.

**CLI:**

```bash
patent-screener screen ideas/my_idea.txt
```

Writes `reports/my_idea.md` and `reports/my_idea.html`.

## Configuration

API keys are read from environment variables or a `.env` file (never committed). See `.env.example` for the expected variable names. The tool fails gracefully and skips a data source when its key is missing.

`USPTO_API_KEY` requires a USPTO.gov account with MFA enabled - sign in at
[data.uspto.gov](https://data.uspto.gov) and generate a key from "My ODP" /
"My API Key" on your account page. This is separate from TSDR trademark keys.

## Cost

Every Claude API call (idea extraction, claim comparison) costs real money,
billed through your Anthropic account - this is separate from any Claude.ai
subscription. Both the CLI and the web UI print a token count and an estimated
dollar cost for the run (see `src/usage.py`); verify current pricing at
[platform.claude.com/pricing](https://platform.claude.com/docs/en/about-claude/pricing)
since Anthropic changes it over time. USPTO's API itself is free.

## Project layout

```
patent-screener/
  src/
    cli.py          # CLI entry point (screen, serve)
    web.py           # local FastAPI web UI
    pipeline.py       # shared extract -> search -> compare pipeline
    jobs.py           # in-memory background job + live progress state
    history.py        # sqlite-backed history of past runs
    extract.py      # idea -> elements + queries
    sources/        # one adapter per data source
    compare.py      # claim vs idea element comparison
    report.py       # markdown + HTML report builder
    usage.py         # token/cost tracking
    cache.py        # sqlite cache
    templates/        # shared HTML templates (file report + web UI)
  tests/
  ideas/            # input idea files (gitignored)
  reports/          # output reports (gitignored)
```

## Out of scope

- Legal opinions or infringement conclusions
- Non-patent prior art searching
- Filing or drafting patent applications

## Roadmap

- A page to set up recurring scheduled searches for recently expired patents
  in chosen patent categories (not built yet)
- A second data source (Lens or BigQuery) with CPC-based search

## License

GPL-3.0 - see [LICENSE](LICENSE).
