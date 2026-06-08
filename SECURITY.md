# Security Policy

## Sensitive data model

Email exports may contain credentials, legal material, health data, financial data, and personal
identifiers. Mail2MD excludes its default download, conversion, profile, secret, and email-export
paths from Git. Conversion is local; browser screenshots are sent only during an explicitly
executed Gemini Computer Use run.

## Enforced browser controls

- The browser is visible and uses a dedicated extension-disabled profile.
- The operator signs in manually; the model never receives or types credentials.
- Main-frame requests are rejected before transmission unless the hostname is allowlisted.
- Login hosts are removed from the runtime allowlist once the mailbox is ready.
- Model typing is limited to the exact approved mailbox search query.
- Unsupported actions and unknown or blocking safety decisions terminate the run.
- Downloads are accepted only from a mailbox page, only as `.eml`, and only up to the configured
  message limit.
- Download and conversion filenames are collision-safe; existing divergent output is not
  overwritten.
- Runs are bounded by validated message and step limits and require an explicit completion status.

Computer Use remains a model-driven Preview capability. The deterministic policy layer limits its
authority, and the visible browser provides an immediate stop control.

## Reporting

Do not open a public issue containing real email data. Use GitHub private vulnerability reporting
for this repository.
