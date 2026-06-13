# Mail2MD Computer Use

[![CI](https://github.com/fredm23579/mail2md-computer-use/actions/workflows/ci.yml/badge.svg)](https://github.com/fredm23579/mail2md-computer-use/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Gemini Computer Use](https://img.shields.io/badge/Gemini-Computer%20Use-8E75B2?logo=google&logoColor=white)](https://ai.google.dev/gemini-api/docs/computer-use)
[![Tests](https://img.shields.io/badge/tests-20%20passing-brightgreen)](tests)
[![Typed: mypy strict](https://img.shields.io/badge/typed-mypy%20strict-2A6DB2)](https://mypy-lang.org/)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-Ruff-D7FF64?logo=ruff)](https://docs.astral.sh/ruff/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

Policy-gated Gmail and Outlook web export plus deterministic conversion of `.eml`, `.msg`,
`.mbox`, and `.mbx` files into precise, AI-ready Markdown.

## What it does

Mail2MD separates adaptive browser work from deterministic document conversion:

1. **Browser export:** Gemini Computer Use operates a visible Playwright browser, within enforced
   hostname, action, text-entry, download-type, message-count, and step-count limits.
2. **Local conversion:** Python parses exported mail without sending message contents to a model.
   It writes structured Markdown and byte-identical attachment files with SHA-256 checksums.

The converter preserves message metadata, display-name addresses, plain text, exact original HTML,
raw headers, inline CID relationships, nested attached messages, and attachment bytes. Content-based
identities and exclusive writes prevent distinct messages or attachments from overwriting each
other.

## Safety controls

- Dry-run browser commands unless `--execute` is supplied
- Manual login; the model never receives passwords or MFA codes
- Pre-request main-frame hostname enforcement, then mailbox-only navigation after login
- Prompt-injection detection plus deterministic action and typed-text restrictions
- Unknown or blocking Gemini safety decisions terminate the run
- Only mailbox-originated `.eml` downloads are accepted
- Collision-safe download promotion and conversion output
- Validated limits and explicit model completion status
- Sensitive runtime paths and email formats excluded by `.gitignore`

See [SECURITY.md](SECURITY.md) for the full boundary.

## Installation

```bash
git clone https://github.com/fredm23579/mail2md-computer-use.git
cd mail2md-computer-use
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
playwright install chromium
```

For browser export, set a Gemini Developer API key in the environment:

```bash
export GEMINI_API_KEY="your-api-key"
```

Local file conversion does not require an API key or browser.

## Convert email files

```bash
mail2md convert-files ./mail-downloads --output ./mail2md-output
```

The input may be one supported file or a directory. Directory conversion is recursive by default.

```text
mail2md-output/
└── quarterly-status-next-steps-a1b2c3d4e5f6/
    ├── email.md
    └── attachments/
        └── notes.txt
```

Each `email.md` contains:

- YAML front matter with source and message metadata
- A literal plain-text body or readable HTML-to-Markdown body
- Exact original HTML in a fenced source section when present
- Attachment links, MIME types, byte counts, and SHA-256 checksums
- Exact raw headers in an injection-safe adaptive fence

## Export from Gmail or Outlook web

Review the no-side-effect dry run:

```bash
mail2md browser-export \
  --provider gmail \
  --query 'after:2026/01/01 from:billing@example.com has:attachment' \
  --max-messages 10
```

Start the visible, supervised run:

```bash
mail2md browser-export \
  --provider gmail \
  --query 'after:2026/01/01 from:billing@example.com has:attachment' \
  --max-messages 10 \
  --execute
```

Export and convert in one command:

```bash
mail2md export-and-convert \
  --provider outlook \
  --query 'from:billing@example.com received>=2026-01-01' \
  --output ./mail2md-output \
  --max-messages 10 \
  --execute
```

The browser opens to the selected provider. Complete sign-in manually, confirm the mailbox is open,
and keep the visible window available as the immediate stop control.

## Desktop mail clients

Gemini Computer Use targets browser environments. Mail2MD directly converts files exported by
standalone clients without using broad OS-level mouse automation:

- Outlook: `.msg` or `.eml`
- Thunderbird: `.eml` or `.mbox`
- Apple Mail and other Unix-style clients: `.mbox` or `.eml`

## Conversion guarantees

- Source files are never modified.
- Attachments are stored byte-for-byte and never executed.
- Distinct normalized content produces distinct output identities.
- Existing divergent output and symlinked output boundaries are rejected.
- Plain text and raw headers are fenced as literal data, not interpreted as generated Markdown.
- HTML is provided both as readable Markdown and exact fenced source.
- Nested attached emails remain attachments rather than being merged into the parent body.

Markdown cannot reproduce browser CSS layout, but the exact HTML source remains in the output so no
source representation is discarded.

## Development

```bash
ruff check .
mypy src
pytest
python -m build
```

The test suite covers parsing, nested messages, display-name addresses, CID links, output identity,
case-insensitive filename collisions, symlink rejection, Markdown injection boundaries, browser
host policy, model text restrictions, safety decisions, scroll semantics, download filtering, and
runtime limits.

## Known Limitations

- Live provider/API paths may require credentials, network access, and manual setup that local tests do not exercise.
- Passing local tests does not prove legal, filing, privacy, or production readiness.
- Claims in this README are governed by `docs/claim_matrix.md`; incomplete or optional features must stay labeled as such.


## Documentation Truthfulness

This repository follows the Truthful Build Doctrine in `docs/truthful-build-doctrine.md`. Public claims are tracked in `docs/claim_matrix.md`, and public releases should complete `docs/release_truthfulness_checklist.md`. Unsupported claims are defects.

Run the local gate before publishing README-affecting changes:

```bash
scripts/truthfulness.sh
```


## License

Apache License 2.0. See [LICENSE](LICENSE).
