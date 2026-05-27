const URL_RE = /https?:\/\/[^\s<>"')\]]+/gi;

const $ = (id) => document.getElementById(id);

function settings() {
  return {
    base: (localStorage.getItem("lv_base") || window.location.origin).replace(/\/$/, ""),
    key: localStorage.getItem("lv_api_key") || "",
  };
}

function saveSettings(base, key) {
  localStorage.setItem("lv_base", base.replace(/\/$/, ""));
  localStorage.setItem("lv_api_key", key);
}

function extractSharedUrl(params) {
  const direct = params.get("url");
  if (direct && direct.startsWith("http")) {
    return direct.trim();
  }
  const text = [params.get("text"), params.get("title")].filter(Boolean).join(" ");
  const matches = text.match(URL_RE);
  return matches ? matches[0].replace(/[.,);]+$/, "") : null;
}

async function saveLink(url, note) {
  const { base, key } = settings();
  const headers = { "Content-Type": "application/json" };
  if (key) {
    headers["X-Link-Vault-Key"] = key;
  }
  const response = await fetch(`${base}/api/items`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      url,
      note: note || null,
      import_source: "android_share",
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Save failed (${response.status})`);
  }
  return response.json();
}

function showSetup() {
  $("setupPanel").classList.remove("hidden");
  const { base, key } = settings();
  $("serverUrl").value = base === window.location.origin ? "" : base;
  $("apiKey").value = key;
}

$("saveSetupBtn").addEventListener("click", () => {
  const base = $("serverUrl").value.trim() || window.location.origin;
  const key = $("apiKey").value.trim();
  if (!key) {
    alert("API key is required on deployed servers.");
    return;
  }
  saveSettings(base, key);
  $("setupPanel").classList.add("hidden");
  run();
});

$("retryBtn").addEventListener("click", () => run());

async function run() {
  const params = new URLSearchParams(window.location.search);
  const url = extractSharedUrl(params);
  const note = params.get("text") || params.get("title") || null;
  const { key } = settings();

  $("openDash").href = settings().base + "/";

  if (!key && window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
    $("headline").textContent = "Setup required";
    $("detail").textContent = "Add your API key once, then share from LinkedIn again.";
    showSetup();
    return;
  }

  if (!url) {
    $("headline").textContent = "No link found";
    $("detail").textContent = "Share a page URL from LinkedIn or your browser.";
    $("retryBtn").classList.remove("hidden");
    return;
  }

  $("urlPreview").textContent = url;
  $("headline").textContent = "Saving…";
  $("detail").textContent = "";

  try {
    const item = await saveLink(url, note);
    $("headline").textContent = "Saved";
    $("detail").innerHTML = `<span class="ok">Added to Link Vault.</span> Bucket: <strong>${item.bucket || "processing…"}</strong>`;
    if (item.status === "pending") {
      $("detail").textContent += " AI grouping runs in a few seconds.";
    }
  } catch (error) {
    $("headline").textContent = "Could not save";
    $("detail").innerHTML = `<span class="err">${error.message}</span>`;
    $("retryBtn").classList.remove("hidden");
    if (String(error.message).includes("401")) {
      showSetup();
    }
  }
}

run();
