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
cp .env.example .env
# fill in your API keys
pip install -e .
```

## Configuration

API keys are read from environment variables or a `.env` file (never committed). See `.env.example` for the expected variable names. The tool fails gracefully and skips a data source when its key is missing.

## Project layout

```
patent-screener/
  src/
    cli.py          # entry point
    extract.py      # idea -> elements + queries
    sources/        # one adapter per data source
    compare.py      # claim vs idea element comparison
    report.py       # markdown report builder
    cache.py        # sqlite cache
  tests/
  ideas/            # input idea files (gitignored)
  reports/          # output reports (gitignored)
```

## Out of scope

- Legal opinions or infringement conclusions
- Non-patent prior art searching
- Filing or drafting patent applications

## License

GPL-3.0 - see [LICENSE](LICENSE).
