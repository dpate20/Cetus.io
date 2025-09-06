// Extract Gmail email when a message view is open. We use a MutationObserver
// because Gmail is a SPA and updates the DOM without page reloads.

(function () {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  function extractEmailFields() {
    // Subject: Gmail uses h2.hP in message view
    const subjectEl = document.querySelector("h2.hP");
    const subject = subjectEl ? subjectEl.textContent.trim() : "";

    // From: sender display name / email is often in .gD
    const fromEl = document.querySelector("span.gD");
    const from = fromEl ? (fromEl.getAttribute("email") || fromEl.textContent.trim()) : "";

    // Body: message content divs typically have classes a3s aiL
    // We'll choose the largest a3s block (the actual message body)
    const bodyNodes = Array.from(document.querySelectorAll("div.a3s"));
    let body = "";
    if (bodyNodes.length) {
      let bestNode = bodyNodes[0];
      let bestLen = bestNode.innerText.length;
      for (const n of bodyNodes) {
        const len = n.innerText.length;
        if (len > bestLen) { bestLen = len; bestNode = n; }
      }
      body = bestNode.innerText.trim();
    } else {
      // Fallback to main area text if selector fails
      const main = document.querySelector("div[role='main']");
      body = main ? main.innerText.trim() : "";
    }

    return { subject, from, body, ts: Date.now() };
  }

  async function extractAndStore() {
    await wait(200); // let Gmail finish rendering
    const email = extractEmailFields();

    // Only store if we have a meaningful body or subject
    if ((email.subject && email.subject.length > 0) || (email.body && email.body.length > 20)) {
      chrome.storage.local.set({ currentEmail: email });
    }
  }

  // Initial try
  extractAndStore();

  // Watch for DOM mutations that indicate new message opened
  const obs = new MutationObserver(() => extractAndStore());
  obs.observe(document.body, { childList: true, subtree: true });
})();
