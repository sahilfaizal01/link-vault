const saveBtn = document.getElementById("saveBtn");
const statusEl = document.getElementById("status");
const noteEl = document.getElementById("note");
const apiUrlEl = document.getElementById("apiUrl");
const apiKeyEl = document.getElementById("apiKey");
const pageTitleEl = document.getElementById("pageTitle");
const openDashboard = document.getElementById("openDashboard");

let currentTab = null;

chrome.storage.sync.get(["apiUrl", "apiKey"], (data) => {
  if (data.apiUrl) {
    apiUrlEl.value = data.apiUrl;
    openDashboard.href = data.apiUrl;
  }
  if (data.apiKey) {
    apiKeyEl.value = data.apiKey;
  }
});

chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  currentTab = tabs[0];
  if (!currentTab) {
    pageTitleEl.textContent = "No active tab found.";
    saveBtn.disabled = true;
    return;
  }
  pageTitleEl.textContent = currentTab.title || currentTab.url;
});

saveBtn.addEventListener("click", async () => {
  if (!currentTab?.url) return;

  const apiUrl = apiUrlEl.value.replace(/\/$/, "");
  statusEl.className = "";
  statusEl.textContent = "Saving...";
  saveBtn.disabled = true;

  try {
    const apiKey = apiKeyEl.value.trim();
    await chrome.storage.sync.set({ apiUrl, apiKey });

    const headers = { "Content-Type": "application/json" };
    if (apiKey) {
      headers["X-Link-Vault-Key"] = apiKey;
    }

    const response = await fetch(`${apiUrl}/api/items`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        url: currentTab.url,
        title: currentTab.title,
        note: noteEl.value.trim() || null,
        import_source: "chrome_extension",
      }),
    });

    if (!response.ok) {
      throw new Error(await response.text());
    }

    statusEl.className = "ok";
    statusEl.textContent = "Saved. Open dashboard to see buckets.";
    openDashboard.href = apiUrl;
  } catch (error) {
    statusEl.className = "error";
    statusEl.textContent =
      "Could not reach Link Vault. Start the server and check API URL.";
    console.error(error);
  } finally {
    saveBtn.disabled = false;
  }
});
