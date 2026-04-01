# Citegeist: BibTeX Reference Checker

Checks, standardizes, and upgrades `.bib` files automatically.

## Features

| Feature | Description |
|---------|-------------|
| **Venue standardization** | Detects common spellings of conference/journal names and replaces them with canonical `@String` macros |
| **arXiv → published upgrade** | Searches Semantic Scholar, CrossRef, arXiv, and Perplexity AI to find the formal publication venue for preprints |
| **DuckDuckGo verification** | Confirms every found publication exists on the web to guard against LLM hallucinations |
| **Entry type inference** | Fixes `@misc` → `@article` or `@inproceedings` based on available fields |
| **Missing field detection** | Warns about required fields absent from entries |
| **Duplicate key detection** | Errors on duplicate cite keys |
| **Undefined `@String` detection** | Errors on bare-word macro references not defined anywhere |

## Installation

Requires Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

This installs the `bib-check` command into a local `.venv`.

## Usage

```bash
uv run bib-check references.bib
```

**Options:**

| Flag | Description |
|------|-------------|
| `-o FILE` | Output `.bib` file (default: `<input>_fixed.bib`) |
| `-r FILE` | Output report file in Markdown (default: `<input>_report.md`) |
| `--offline` | Skip all network lookups |
| `--no-upgrade` | Skip arXiv → published upgrade (venue standardization still runs) |
| `--perplexity-key KEY` | Perplexity AI API key (overrides `PERPLEXITY_API_KEY` env var) |
| `-v` | Verbose: print search progress to stderr |

## Perplexity AI integration

Perplexity AI has web-search capabilities and can find publication venues that
structured APIs (Semantic Scholar, CrossRef) may not index yet.

1. Get a key at <https://www.perplexity.ai/settings/api>
2. Pass it via environment variable or CLI flag:

```bash
export PERPLEXITY_API_KEY=pplx-...
uv run bib-check references.bib

# or inline:
uv run bib-check references.bib --perplexity-key pplx-...
```

Every result from Perplexity is **verified via DuckDuckGo** before being
accepted, so hallucinated DOIs / venues are discarded automatically.

## Search pipeline

For each arXiv preprint the tool runs the following pipeline (in order,
stopping at the first confirmed published result):

```
1. Semantic Scholar  (structured API, most complete venue data)
2. CrossRef          (DOI-indexed published works)
3. arXiv             (journal_ref / DOI sometimes present)
4. Perplexity AI     (web search + LLM; requires API key)
   └→ DuckDuckGo     (verifies result to catch hallucinations)
5. DuckDuckGo        (soft-verify S2 / CrossRef results too)
```

Papers that cannot be confirmed as published are flagged for **manual review**
in the report.

## Output

- `references_fixed.bib` – cleaned bib with canonical `@String` macros and upgraded entries
- `references_report.md` – Markdown report with all changes and issues

### @String macros emitted

Only macros that are actually used in the output file are emitted.
The canonical set includes: CVPR, ICCV, ECCV, NeurIPS, ICML, ICLR, AAAI,
IJCAI, AISTATS, SIGGRAPH, TOG, PAMI, IJCV, TIP, TVCG, TMM, TCSVT, WACV,
ACMMM, BMVC, ICPR, CGF, EGSR, ARXIV, and more.

## Project structure

```
/
├── pyproject.toml
└── bib_checker/
    ├── cli.py       – argument parsing and entry point
    ├── checker.py   – main checking logic
    ├── parser.py    – BibTeX parser (no external deps)
    ├── writer.py    – BibTeX serializer
    ├── search.py    – arXiv / S2 / CrossRef / Perplexity / DDG backends
    ├── strings.py   – canonical @String definitions and alias table
    ├── datatypes.py – shared data classes
    └── report.py    – Markdown report generator
```
