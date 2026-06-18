# plugin-web-access

Live web access for [Luna](https://github.com/huemorgan/luna) — search the web,
fetch pages as readable text, and make arbitrary HTTP requests, all from the
chat.

This is a **Luna plugin** built against the Luna Plugin SDK (`luna_sdk`) v0. It
imports nothing from `luna.*` — only the stable SDK surface — so it installs
from the Luna marketplace and runs without being part of Luna core.

## Install

In Luna: **Marketplace → Luna Official → plugin-web-access → Install**.

## What it does

| Tool | Purpose |
|---|---|
| `web_search` | Live web search via Tavily (default) or Google Custom Search. Returns a concise answer plus source results. |
| `web_fetch` | Fetch a URL and return its readable text (chrome/scripts stripped). |
| `http_request` | Generic HTTP client (GET/POST/PUT/PATCH/DELETE) for calling REST APIs. |

## Credentials

API keys resolve **vault-first** via the injected `ctx.vault`, then fall back to
environment variables:

| Credential (vault) | Env fallback |
|---|---|
| `tavily_api_key` | `LUNA_TAVILY_API_KEY` |
| `google_search_api_key` | `LUNA_GOOGLE_SEARCH_API_KEY` |
| `google_search_cx` | `LUNA_GOOGLE_SEARCH_CX` |
| — | `LUNA_WEB_SEARCH_PROVIDER` (`tavily` \| `google`, default `tavily`) |

Store the keys in **Settings → Credentials**, or set the env vars. No key →
`web_search` returns a friendly "not configured" message instead of failing.

## Layout

```
plugin_web_access/
  __init__.py        # the plugin (luna_sdk only)
  search.py          # web_search dispatch (Tavily / Google), vault-first creds
  fetch.py           # web_fetch — page → readable text
  http_client.py     # http_request — generic REST client
  safety.py          # SSRF / private-network guards (pure stdlib)
  luna-plugin.toml   # the data manifest the marketplace reads
```

## License

MIT — see [LICENSE](./LICENSE).
