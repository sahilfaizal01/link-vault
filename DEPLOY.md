# Deploy Link Vault on Render + Android Share

## 1. Push to GitHub

Create a repo containing the `link-vault/` folder (repo root can be `link-vault` itself).

## 2. Create Render service

1. Go to [render.com](https://render.com) → **New** → **Blueprint** (or Web Service).
2. Connect your GitHub repo.
3. If not using Blueprint, set:
   - **Build:** `pip install -r requirements.txt`
   - **Start:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - **Health check:** `/api/health`

Or click **Apply Blueprint** if `render.yaml` is at repo root.

## 3. Environment variables (Render dashboard)

| Variable | Value |
|----------|--------|
| `LINK_VAULT_DB` | `/var/data/link_vault.db` |
| `LINK_VAULT_API_KEY` | Generate a long random string (required) |
| `OPENAI_API_KEY` | Optional, for smarter summaries |
| `LINK_VAULT_HOST` | `0.0.0.0` (set automatically in blueprint) |

**Disk:** Attach a **1GB disk** mounted at `/var/data` (Starter plan). Without it, SQLite resets on redeploy.

Copy your public URL, e.g. `https://link-vault-xxxx.onrender.com`.

## 4. Android — Share to Link Vault

1. On your phone, open **Chrome** → go to `https://link-vault-xxxx.onrender.com/share`.
2. Enter **API key** (same as `LINK_VAULT_API_KEY` on Render) → **Save settings**.
3. Chrome menu → **Install app** / **Add to Home screen** (installs the PWA).
4. Open **LinkedIn** → post → **Share** → choose **Link Vault** (or “Share to Link Vault”).
5. You should see “Saved” — bucket appears on the dashboard.

**Tips**

- If Link Vault doesn’t appear in the share sheet, reinstall the PWA from Chrome.
- Use **Copy link** on LinkedIn if Share doesn’t pass a URL.
- Free Render services **sleep** after inactivity; first save may take ~30s to wake.

## 5. Desktop Chrome extension (optional)

1. Load `extension/` unpacked in `chrome://extensions`.
2. Set **API URL** to your Render URL.
3. Set **API key** to the same `LINK_VAULT_API_KEY`.
4. Reload extension after changing URL.

## 6. Dashboard API key

On the main dashboard (`/`), open **Server settings** and paste the same API key so lists/imports work.

## Local development

Leave `LINK_VAULT_API_KEY` empty — no auth required on localhost.

```bash
cd link-vault
source .venv/bin/activate
python -m backend.main
```
