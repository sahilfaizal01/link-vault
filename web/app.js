const API = "";

let activeBucket = null;
let searchTimer = null;

const $ = (id) => document.getElementById(id);

function apiHeaders(extra = {}) {
  const headers = { "Content-Type": "application/json", ...extra };
  const key = localStorage.getItem("lv_api_key");
  if (key) {
    headers["X-Link-Vault-Key"] = key;
  }
  return headers;
}

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: apiHeaders(options.headers || {}),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

function formatCapturedAt(iso) {
  if (!iso) return "Unknown time";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    weekday: "short",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatSourceLabel(item) {
  const parts = [];
  if (item.import_source) {
    parts.push(item.import_source.replaceAll("_", " "));
  }
  if (item.source_type) {
    parts.push(item.source_type.replaceAll("_", " "));
  }
  return parts.join(" · ") || "saved";
}

function renderStats(items, buckets) {
  const processed = items.filter((i) => i.status === "processed").length;
  const pending = items.filter((i) => i.status === "pending").length;
  $("stats").innerHTML = `
    <div class="stat-card"><strong>${items.length}</strong><span>Total saved</span></div>
    <div class="stat-card"><strong>${buckets.length}</strong><span>Active buckets</span></div>
    <div class="stat-card"><strong>${processed}</strong><span>Processed</span></div>
    <div class="stat-card"><strong>${pending}</strong><span>Processing</span></div>
  `;
}

function renderBucketFilters(buckets) {
  const chips = [
    `<button class="chip ${activeBucket ? "" : "active"}" data-bucket="">All</button>`,
    ...buckets.map(
      (b) =>
        `<button class="chip ${activeBucket === b.bucket ? "active" : ""}" data-bucket="${escapeHtml(
          b.bucket
        )}">${escapeHtml(b.bucket)} (${b.count})</button>`
    ),
  ];
  $("bucketFilters").innerHTML = chips.join("");
  $("bucketFilters").querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      activeBucket = chip.dataset.bucket || null;
      loadItems();
      loadBuckets();
    });
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderItems(items) {
  if (!items.length) {
    $("itemsList").innerHTML = `<p class="summary">No links yet. Save one above or use the Chrome extension.</p>`;
    return;
  }

  $("itemsList").innerHTML = items
    .map((item) => {
      const title = escapeHtml(item.title || item.url);
      const tags = (item.tags || [])
        .map((tag) => `<span class="pill">${escapeHtml(tag)}</span>`)
        .join("");
      return `
        <article class="item-card" data-id="${item.id}">
          <h3><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${title}</a></h3>
          <div class="meta-row">
            <span class="pill bucket-pill">${escapeHtml(item.bucket || "Unsorted")}</span>
            <span class="pill captured" title="When this link was saved">Captured ${escapeHtml(
              formatCapturedAt(item.saved_at)
            )}</span>
            <span class="pill muted">${escapeHtml(formatSourceLabel(item))}</span>
            <span class="pill ${item.status === "pending" ? "pending" : "muted"}">${escapeHtml(
              item.status
            )}</span>
          </div>
          ${item.summary ? `<p class="summary">${escapeHtml(item.summary)}</p>` : ""}
          ${
            item.why_it_matters
              ? `<p class="summary"><strong>Why:</strong> ${escapeHtml(item.why_it_matters)}</p>`
              : ""
          }
          ${tags ? `<div class="tag-row">${tags}</div>` : ""}
          <div class="item-actions">
            <button class="btn secondary reprocess-btn" data-id="${item.id}">Reprocess</button>
            <button class="btn danger delete-btn" data-id="${item.id}">Delete</button>
          </div>
        </article>
      `;
    })
    .join("");

  $("itemsList").querySelectorAll(".reprocess-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      await api(`/api/items/${btn.dataset.id}/reprocess`, { method: "POST" });
      await refreshAll();
    });
  });

  $("itemsList").querySelectorAll(".delete-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("Delete this saved link?")) return;
      await api(`/api/items/${btn.dataset.id}`, { method: "DELETE" });
      await refreshAll();
    });
  });
}

function renderDigest(digest) {
  $("digestPanel").classList.remove("hidden");
  const insights = (digest.top_insights || [])
    .map((line) => `<li>${escapeHtml(line)}</li>`)
    .join("");
  const readNext = (digest.read_next || [])
    .map(
      (item) =>
        `<li><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(
          item.title || item.url
        )}</a> — ${escapeHtml(item.why || item.bucket || "")}</li>`
    )
    .join("");
  const buckets = (digest.buckets || [])
    .map(
      (b) =>
        `<li><strong>${escapeHtml(b.name)}</strong> (${b.count}) — ${escapeHtml(
          b.highlight || ""
        )}</li>`
    )
    .join("");

  $("digestContent").innerHTML = `
    <div class="digest-box">
      <h3>${escapeHtml(digest.headline || "Digest")}</h3>
      <p class="summary">${escapeHtml(digest.overview || "")}</p>
      ${insights ? `<h4>Top insights</h4><ul class="digest-list">${insights}</ul>` : ""}
      ${readNext ? `<h4>Read next</h4><ul class="digest-list">${readNext}</ul>` : ""}
      ${buckets ? `<h4>By bucket</h4><ul class="digest-list">${buckets}</ul>` : ""}
    </div>
  `;
}

async function loadBuckets() {
  const buckets = await api("/api/buckets");
  renderBucketFilters(buckets);
  return buckets;
}

async function loadItems() {
  const params = new URLSearchParams();
  if (activeBucket) params.set("bucket", activeBucket);
  const search = $("searchInput").value.trim();
  if (search) params.set("search", search);
  const query = params.toString() ? `?${params}` : "";
  return api(`/api/items${query}`);
}

async function refreshAll() {
  const [items, buckets] = await Promise.all([loadItems(), loadBuckets()]);
  renderStats(items, buckets);
  renderItems(items);
}

$("saveForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const status = $("saveStatus");
  status.className = "status";
  status.textContent = "Saving and processing...";

  try {
    await api("/api/items", {
      method: "POST",
      body: JSON.stringify({
        url: $("urlInput").value.trim(),
        note: $("noteInput").value.trim() || null,
        import_source: "web",
      }),
    });
    $("urlInput").value = "";
    $("noteInput").value = "";
    status.className = "status ok";
    status.textContent = "Saved. AI grouping will appear in a few seconds.";
    setTimeout(refreshAll, 1200);
    setTimeout(refreshAll, 3500);
  } catch (error) {
    status.className = "status error";
    status.textContent = error.message;
  }
});

$("searchInput").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(refreshAll, 250);
});

$("refreshBtn").addEventListener("click", refreshAll);

$("reclassifyBtn").addEventListener("click", async () => {
  if (!confirm("Reclassify every saved link into the new buckets? This may take a minute.")) {
    return;
  }
  $("reclassifyBtn").disabled = true;
  try {
    const result = await api("/api/reclassify-all", { method: "POST" });
    alert(`Reclassified ${result.reclassified} links.`);
    await refreshAll();
  } catch (error) {
    alert(error.message);
  } finally {
    $("reclassifyBtn").disabled = false;
  }
});

$("digestBtn").addEventListener("click", async () => {
  $("digestBtn").disabled = true;
  try {
    const digest = await api("/api/digest?days=14");
    renderDigest(digest);
  } finally {
    $("digestBtn").disabled = false;
  }
});

async function uploadImport(endpoint, file, statusEl) {
  const form = new FormData();
  form.append("file", file);
  statusEl.className = "status";
  statusEl.textContent = "Importing and processing links...";
  const headers = {};
  const key = localStorage.getItem("lv_api_key");
  if (key) {
    headers["X-Link-Vault-Key"] = key;
  }
  const response = await fetch(`${API}${endpoint}?process=true`, {
    method: "POST",
    headers,
    body: form,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Import failed (${response.status})`);
  }
  return response.json();
}

$("whatsappImportBtn").addEventListener("click", async () => {
  const file = $("whatsappFile").files[0];
  const status = $("importStatus");
  if (!file) {
    status.className = "status error";
    status.textContent = "Choose a WhatsApp .txt export first.";
    return;
  }
  try {
    const result = await uploadImport("/api/import/whatsapp", file, status);
    status.className = "status ok";
    status.textContent = `WhatsApp: ${result.found_urls} URLs (${result.created} new, ${result.updated} updated). Processing…`;
    setTimeout(refreshAll, 2000);
  } catch (error) {
    status.className = "status error";
    status.textContent = error.message;
  }
});

$("googleChatImportBtn").addEventListener("click", async () => {
  const file = $("googleChatFile").files[0];
  const status = $("importStatus");
  if (!file) {
    status.className = "status error";
    status.textContent = "Choose a Google Chat export file first.";
    return;
  }
  try {
    const result = await uploadImport("/api/import/google-chat", file, status);
    status.className = "status ok";
    status.textContent = `Google Chat: ${result.found_urls} URLs (${result.created} new, ${result.updated} updated).`;
    setTimeout(refreshAll, 2000);
  } catch (error) {
    status.className = "status error";
    status.textContent = error.message;
  }
});

$("pasteImportBtn").addEventListener("click", async () => {
  const text = $("pasteInput").value.trim();
  const status = $("importStatus");
  if (!text) {
    status.className = "status error";
    status.textContent = "Paste chat text with URLs first.";
    return;
  }
  status.className = "status";
  status.textContent = "Importing pasted URLs...";
  try {
    const result = await api("/api/import/paste", {
      method: "POST",
      body: JSON.stringify({ text, source: "paste", process: true }),
    });
    status.className = "status ok";
    status.textContent = `Paste: ${result.found_urls} URLs (${result.created} new).`;
    $("pasteInput").value = "";
    setTimeout(refreshAll, 2000);
  } catch (error) {
    status.className = "status error";
    status.textContent = error.message;
  }
});

$("saveSettingsBtn")?.addEventListener("click", () => {
  const key = $("settingsApiKey").value.trim();
  localStorage.setItem("lv_api_key", key);
  const base = $("settingsBaseUrl").value.trim();
  if (base) {
    localStorage.setItem("lv_base", base.replace(/\/$/, ""));
  }
  $("settingsStatus").textContent = "Settings saved.";
  $("settingsStatus").className = "status ok";
});

(function loadSettings() {
  const key = localStorage.getItem("lv_api_key") || "";
  const base = localStorage.getItem("lv_base") || "";
  if ($("settingsApiKey")) $("settingsApiKey").value = key;
  if ($("settingsBaseUrl")) $("settingsBaseUrl").value = base;
})();

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/assets/sw.js").catch(() => {});
}

refreshAll();
setInterval(refreshAll, 15000);
