# 001 — validate every HTTP destination and bound returned data

Status: owner authorized, 2026-09-16. Branch `codex/improve-long-tasks`. The public source repo is at 0.2.4; the tested default 0.3.0 artifact adds newer fetch/HTTP modules. Import those exact default-profile files first, then publish code and data manifests consistently as 0.3.1.

dojoP baseline: `WEB-REDIRECT` follows a public URL to loopback without checking the new destination; `WEB-JSON-CAP` returns a 100k-character body alongside a larger structured JSON object. Require manual redirect hops with a guard before each request, reject unsafe schemes/too many hops, and cap every returned representation. Keep ordinary public fetches and small JSON working. Run Web contracts and source tests; record the artifact-to-source import and limits in `execution_summary.md`.
