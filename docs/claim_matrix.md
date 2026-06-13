# README Claim Matrix

| README claim | Evidence in repo | Verification command | Status |
| --- | --- | --- | --- |
| Converts `.eml`, `.msg`, `.mbox`, `.mbx` to Markdown | `src/mail2md/`, `tests/` | `python -m pytest` | Implemented for covered fixtures |
| Browser export is policy-gated | `src/mail2md/browser_agent.py`, `tests/test_browser_policy.py` | `python -m pytest` | Implemented policy checks; live provider runs require credentials/manual login |
| Source files are not modified by conversion | `src/mail2md/converter.py`, tests | `python -m pytest` | Implemented for tested conversion paths |
| Gemini browser export works against live mailboxes | `src/mail2md/browser_agent.py` | `manual credentialed run` | Optional/live; not covered by local tests |

Last local test evidence: `.venv/bin/python -m pytest` produced `20 passed in 0.54s` on 2026-06-13 in this workspace.
