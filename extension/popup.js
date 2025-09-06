(function () {
  const $ = (id) => document.getElementById(id);
  const apiUrlInput = $("apiUrl");
  const subjectInput = $("subject");
  const fromInput = $("from");
  const bodyInput = $("emailText");
  const resultEl = $("result");

  // Load saved URL + last scraped email
  chrome.storage.local.get(["apiUrl", "currentEmail"], (res) => {
    apiUrlInput.value = res.apiUrl || "http://localhost:5000";
    if (res.currentEmail) {
      subjectInput.value = res.currentEmail.subject || "";
      fromInput.value = res.currentEmail.from || "";
      bodyInput.value = res.currentEmail.body || "";
    }
  });

  // Persist API URL
  apiUrlInput.addEventListener("change", () => {
    chrome.storage.local.set({ apiUrl: apiUrlInput.value });
  });

  // Scrape Gmail
  $("loadFromGmail").addEventListener("click", async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !/^https:\/\/mail\.google\.com/.test(tab.url || "")) {
      resultEl.textContent = "Open a Gmail message first.";
      return;
    }
    try {
      await chrome.tabs.sendMessage(tab.id, { type: "SCRAPE_GMAIL" });
      const got = await chrome.storage.local.get(["currentEmail"]);
      const email = got.currentEmail || {};
      subjectInput.value = email.subject || "";
      fromInput.value = email.from || "";
      bodyInput.value = email.body || "";
      resultEl.textContent = "Loaded from Gmail.";
    } catch (e) {
      console.error(e);
      resultEl.textContent = "Could not read Gmail content on this page.";
    }
  });

  // Predict
  $("checkBtn").addEventListener("click", async () => {
    const base = apiUrlInput.value.replace(/\/+$/, "");
    const payload = {
      subject: subjectInput.value || "",
      from: fromInput.value || "",
      text: bodyInput.value || "",
    };
    resultEl.textContent = "Checking…";
    try {
      const resp = await fetch(base + "/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      const label = data.prediction || "Unknown";
      const conf = (typeof data.confidence === "number") ? ` (${(data.confidence*100).toFixed(1)}%)` : "";
      const isPhish = /phish/i.test(label);
      resultEl.innerHTML = `<span id="badge" class="${isPhish ? "bad" : "ok"}">Prediction: ${label}${conf}</span>`;
    } catch (e) {
      console.error(e);
      resultEl.textContent = "Error contacting API. Is it running?";
    }
  });

  // Report helper
  async function report(label) {
    const base = apiUrlInput.value.replace(/\/+$/, "");
    const payload = {
      subject: subjectInput.value || "",
      from: fromInput.value || "",
      text: bodyInput.value || "",
      label
    };
    resultEl.textContent = "Reporting…";
    try {
      const resp = await fetch(base + "/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      if (data.ok) {
        resultEl.textContent = `Thanks! Added as "${label}". Samples in DB: ${data.reports}. Model retrained.`;
      } else {
        resultEl.textContent = "Report failed: " + (data.error || "unknown error");
      }
    } catch (e) {
      console.error(e);
      resultEl.textContent = "Could not reach backend to report.";
    }
  }

  $("reportPhish").addEventListener("click", () => report("phish"));
  $("reportHam").addEventListener("click", () => report("ham"));
})();
