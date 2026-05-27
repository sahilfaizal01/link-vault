# Link Vault (MVP)

Save LinkedIn posts, blogs, and article links in one place. Link Vault fetches metadata, groups links into topic buckets, and generates a readable digest.

## What is included

- **Web dashboard** at `http://127.0.0.1:8787`
- **REST API** for saving and listing links
- **Chrome extension** for one-click capture from any tab
- **SQLite storage** (local, no cloud DB required)
- **AI enrichment** when `OPENAI_API_KEY` or AMD `LLM_*` env vars are set
- **Heuristic fallback** when no LLM is configured
- **WhatsApp import** from exported `.txt` chat (your “message yourself” chat)
- **Google Chat import** from Takeout JSON or pasted messages

### Default buckets

LinkedIn Profiles · Job Links · GPU Programming · Inference Optimization · Model Architecture · Training · Tips & Tricks · Frameworks & Tools · Papers & Research · Blogs & Articles · News & Announcements · Career & Networking

Each item shows **Captured** date/time (when you saved or imported it). Use **Reclassify all** in the dashboard after bucket changes.

### AI grouping strategy (hybrid, partial)

| Planned | Status |
|--------|--------|
| LLM summary + canonical bucket | Yes |
| Keyword/heuristic fallback | Yes |
| Emerging topic buckets | Yes (`Emerging: …`) |
| Embedding similarity | Not yet |
| URL dedupe | Yes (unique URLs) |
| Priority score | Yes |
| Similar links (heuristic) | Yes |
| Live WhatsApp / Google Chat API | Not yet (export/paste only) |
| Email digest | Not yet |

Check runtime flags: `GET /api/features`

## Deploy (Render + Android share)

See **[DEPLOY.md](DEPLOY.md)** for Render setup, API key, and **Share → Link Vault** on Android.

## Quick start

```bash
cd link-vault
cp .env.example .env
# optional: set OPENAI_API_KEY or LLM_* in .env

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m backend.main
```

Open: http://127.0.0.1:8787

## Load the Chrome extension

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `link-vault/extension` folder
5. Pin **Link Vault**, click it on any page, then **Save this page**

Default API URL in the extension: `http://127.0.0.1:8787`

## API examples

```bash
# Save a link
curl -X POST http://127.0.0.1:8787/api/items \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","note":"good post"}'

# List buckets
curl http://127.0.0.1:8787/api/buckets

# Generate digest
curl http://127.0.0.1:8787/api/digest?days=14
```

## Import WhatsApp links (existing chat)

1. Open your **Message yourself** chat in WhatsApp (or any chat where you dump links).
2. **⋮ → More → Export chat → Without media** (saves a `.txt` file).
3. In the dashboard **Import existing links** section, upload that file.

## Import Google Chat links

**Option A — Google Takeout**

1. Go to [takeout.google.com](https://takeout.google.com).
2. Deselect all, then enable **Google Chat** (JSON).
3. Download and upload the JSON file in the dashboard.

**Option B — Paste**

Copy messages that contain URLs from Google Chat and use **Import from paste**.

## Notes

- LinkedIn and some sites block automated fetching; links are still saved and classified using URL/title/note.
- Data is stored in `link-vault/data/link_vault.db`.
- Live sync with WhatsApp/Google Chat requires OAuth/API setup (Phase 3); exports work today without that.
