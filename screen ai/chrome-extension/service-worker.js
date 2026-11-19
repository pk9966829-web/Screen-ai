const API = "http://127.0.0.1:8001";
const DEVICE_KEY = "vosiPairedDevice";
let checking = false;
let heartbeatInProgress = false;

async function getPairedDevice() {
  const data = await chrome.storage.local.get(DEVICE_KEY);
  return data[DEVICE_KEY] || null;
}

function authHeaders(device) {
  return { Authorization: "Bearer " + device.deviceToken };
}

async function sendHeartbeat() {
  if (heartbeatInProgress) return;
  heartbeatInProgress = true;
  try {
    const device = await getPairedDevice();
    if (!device?.deviceId || !device?.deviceToken) return;
    const response = await fetch(
      API + "/agent/devices/" + encodeURIComponent(device.deviceId) + "/heartbeat",
      { method: "POST", headers: authHeaders(device), cache: "no-store" }
    );
    if (response.status === 401 || response.status === 403) {
      await chrome.storage.local.set({ vosiConnectionState: "revoked" });
      return;
    }
    if (response.ok) {
      await chrome.storage.local.set({ vosiConnectionState: "online", vosiLastHeartbeat: new Date().toISOString() });
    } else {
      await chrome.storage.local.set({ vosiConnectionState: "offline" });
    }
  } catch {
    await chrome.storage.local.set({ vosiConnectionState: "offline" });
  } finally {
    heartbeatInProgress = false;
  }
}

async function reportAgentBrowserResults(message, sender) {
  if (sender.id !== chrome.runtime.id || !sender.url?.startsWith("https://www.flipkart.com/")) {
    throw new Error("Agent results were not sent by the VOSI Flipkart content script.");
  }
  const device = await getPairedDevice();
  if (!device?.deviceToken) throw new Error("Chrome is not paired with VOSI.");
  const products = Array.isArray(message.products) ? message.products.slice(0, 8) : [];
  const success = products.length > 0;
  const response = await fetch(
    API + "/agent/tasks/" + encodeURIComponent(message.taskId) +
      "/steps/" + encodeURIComponent(message.stepId) + "/result",
    {
      method: "POST",
      headers: { ...authHeaders(device), "Content-Type": "application/json" },
      body: JSON.stringify({
        success,
        verified: success,
        receipt: success ? {
          capability: "browser.search_products",
          source: "flipkart-visible-search-results",
          result_count: products.length,
          products
        } : {},
        error: success ? null : "No product cards were detected on the results page."
      })
    }
  );
  if (!response.ok) throw new Error("VOSI rejected the task result (HTTP " + response.status + ").");
  await chrome.storage.local.set({ vosiLastTaskResult: new Date().toISOString() });
  return response.json();
}

async function postAgentTaskResult(device, taskId, stepId, payload) {
  const response = await fetch(API + "/agent/tasks/" + encodeURIComponent(taskId) +
    "/steps/" + encodeURIComponent(stepId) + "/result", {
    method: "POST",
    headers: { ...authHeaders(device), "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error("VOSI rejected the browser task receipt (HTTP " + response.status + ").");
  return response.json();
}

async function executeBrowserInteraction(device, task, step) {
  const args = step.arguments || {};
  const action = String(args.action || "");
  const target = String(args.target || "").trim().slice(0, 120);
  if (!target || !["click", "type", "scroll", "select"].includes(action)) throw new Error("Unsupported or incomplete browser interaction.");
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (!tab?.id || !tab.url) throw new Error("No active Chrome page.");
  const url = new URL(tab.url);
  if (url.protocol !== "https:") throw new Error("VOSI interaction is restricted to HTTPS pages.");
  if (!await chrome.permissions.contains({ origins: [url.origin + "/*"] })) throw new Error("Website permission is missing. Enable the current website in the extension.");
  const result = await chrome.scripting.executeScript({
    target: { tabId: tab.id }, world: "ISOLATED",
    func: ({action, target, text, direction, option}) => {
      const norm = s => String(s || "").replace(/\\s+/g, " ").trim().toLowerCase();
      const visible = el => !!(el && el.getClientRects().length && getComputedStyle(el).visibility !== "hidden" && getComputedStyle(el).display !== "none");
      const labelOf = el => norm(el.innerText || el.getAttribute("aria-label") || el.getAttribute("title") || el.labels?.[0]?.innerText || el.getAttribute("placeholder"));
      const matches = Array.from(document.querySelectorAll("button,[role=button],a,input,textarea,select,[contenteditable=true]")).filter(visible).filter(el => labelOf(el) === norm(target));
      if (action === "scroll") {
        const before = window.scrollY;
        window.scrollBy({top: direction === "down" ? Math.max(250, window.innerHeight * 0.7) : -Math.max(250, window.innerHeight * 0.7), behavior: "instant"});
        return {success: window.scrollY !== before, verified: window.scrollY !== before, evidence: {scroll_before: before, scroll_after: window.scrollY}};
      }
      if (matches.length !== 1) return {success:false, verified:false, error: matches.length ? "Target label is ambiguous." : "Target label not found."};
      const el = matches[0];
      if (action === "click") {
        const label = labelOf(el);
        if (/buy|purchase|checkout|pay|place order|submit|send|delete|remove|confirm|unsubscribe|transfer|book now|save changes|sign in|log in|authorize|grant/i.test(label)) return {success:false, verified:false, error:"This control may have consequential effects and is blocked in the basic interaction stage."};
        if (el.closest("form") && (el.type === "submit" || el.getAttribute("type") === "submit")) return {success:false, verified:false, error:"Form submission is blocked in the basic interaction stage."};
        const oldUrl = location.href, oldText = (document.body?.innerText || "").slice(0, 4000);
        el.click();
        return {success:true, verified:false, evidence:{clicked_label:label, old_url:oldUrl, current_url:location.href, text_changed:oldText !== (document.body?.innerText || "").slice(0,4000)}, note:"Click was dispatched; page-state verification requires a subsequent inspection."};
      }
      if (action === "type") {
        if (!(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el.isContentEditable)) return {success:false,verified:false,error:"Target is not a text-entry field."};
        const type = norm(el.getAttribute("type") || "text");
        const fieldLabel = norm(el.getAttribute("aria-label") || el.labels?.[0]?.innerText || el.placeholder || el.name);
        if (/(password|email|tel|phone|credit|card|cvv|otp|token|secret|url)/i.test(type + " " + fieldLabel)) return {success:false,verified:false,error:"Sensitive or unsupported field type is blocked."};
        if (el instanceof HTMLInputElement && !["text","search"].includes(type)) return {success:false,verified:false,error:"Only text and search fields are allowed."};
        el.focus();
        if (el.isContentEditable) { el.textContent = text; el.dispatchEvent(new InputEvent("input",{bubbles:true,inputType:"insertText",data:text})); }
        else { const setter=Object.getOwnPropertyDescriptor(el.constructor.prototype,"value")?.set; setter?.call(el,text); el.dispatchEvent(new Event("input",{bubbles:true})); el.dispatchEvent(new Event("change",{bubbles:true})); }
        const verified = (el.isContentEditable ? el.textContent : el.value) === text;
        return {success:verified,verified,evidence:{field_label:fieldLabel,character_count:String(text).length,field_value_verified:verified}};
      }
      if (action === "select") {
        if (!(el instanceof HTMLSelectElement)) return {success:false,verified:false,error:"Target is not a select control."};
        const optionMatch = Array.from(el.options).find(o => norm(o.text) === norm(option));
        if (!optionMatch) return {success:false,verified:false,error:"Requested option was not found."};
        el.value=optionMatch.value; el.dispatchEvent(new Event("change",{bubbles:true}));
        const verified = el.value === optionMatch.value;
        return {success:verified,verified,evidence:{field_label:labelOf(el),selected_option:optionMatch.text,selection_verified:verified}};
      }
      return {success:false,verified:false,error:"Unsupported interaction."};
    },
    args: {action,target,text:action==="type" ? String(args.text || "").slice(0,2000) : "",direction:args.direction,option:args.option}
  });
  const evidence = result?.[0]?.result || {};
  await postAgentTaskResult(device, task.task_id, step.step_id, {
    success: !!evidence.success, verified: !!evidence.verified, receipt: evidence.success ? {capability:"browser.interact", action, target, evidence, captured_at:new Date().toISOString()} : {},
    error: evidence.error || (evidence.success && !evidence.verified ? "Action dispatched, but its result was not independently verified." : null)
  });
}

async function executeGeneralBrowserStep(device, task, step) {
  if (step.capability === "browser.interact") {
    await executeBrowserInteraction(device, task, step);
    return;
  }
  if (step.capability === "browser.search_web") {
    const query = String(step.arguments?.query || "").trim().slice(0, 500);
    if (!query) throw new Error("Research query is empty.");
    const response = await fetch(API + "/research/search", {
      method: "POST", headers: { ...authHeaders(device), "Content-Type": "application/json" },
      body: JSON.stringify({ query, count: 5 }), cache: "no-store"
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.success) throw new Error(data.detail || "VOSI web research is unavailable.");
    const results = Array.isArray(data.results) ? data.results.slice(0, 10) : [];
    await postAgentTaskResult(device, task.task_id, step.step_id, {
      success: results.length > 0, verified: results.length > 0,
      receipt: results.length ? { capability: "browser.search_web", provider: data.provider, query: data.query, result_count: results.length, results, citations: results.map(item => item.url), confirmation: "Found " + results.length + " public web sources." } : {},
      error: results.length ? null : "The search provider returned no usable public sources."
    });
    return;
  }
  if (step.capability === "browser.open_tab") {
    const raw = String(step.arguments?.url || "").trim();
    let parsed;
    try { parsed = new URL(raw); } catch { throw new Error("The requested website address is invalid."); }
    if (parsed.protocol !== "https:" || !parsed.hostname || parsed.username || parsed.password || raw.length > 2048) {
      throw new Error("VOSI can open only valid HTTPS website addresses without embedded credentials.");
    }
    const tab = await chrome.tabs.create({ url: parsed.href, active: true });
    await postAgentTaskResult(device, task.task_id, step.step_id, {
      success: true, verified: true,
      receipt: { capability: "browser.open_tab", url: parsed.href, tab_id: tab.id, active: true, confirmation: "Opened " + parsed.hostname + " in a new Chrome tab." }
    });
    return;
  }
  if (step.capability === "browser.inspect_page") {
    const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    if (!tab?.id || !tab.url) throw new Error("No active Chrome webpage to inspect.");
    const pageUrl = new URL(tab.url);
    if (pageUrl.protocol !== "https:") throw new Error("VOSI can inspect only HTTPS websites.");
    const hasPermission = await chrome.permissions.contains({ origins: [pageUrl.origin + "/*"] });
    if (!hasPermission) throw new Error("Website permission is missing. In the extension popup, choose Enable current website first.");
    const injected = await chrome.scripting.executeScript({
      target: { tabId: tab.id }, world: "ISOLATED",
      func: () => {
        const clean = (value, max = 500) => String(value || "").replace(/\\s+/g, " ").trim().slice(0, max);
        const redact = value => clean(value, 16000)
          .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}/gi, "[email redacted]")
          .replace(/(?:\\+?\\d[\\d .()-]{7,}\\d)/g, "[phone redacted]");
        const visible = el => !!(el && el.getClientRects().length && getComputedStyle(el).visibility !== "hidden" && getComputedStyle(el).display !== "none");
        const links = Array.from(document.querySelectorAll("a[href]")).filter(visible).slice(0, 40).map(a => ({ text: clean(a.innerText || a.getAttribute("aria-label"), 180), href: a.href.slice(0, 400) })).filter(a => a.text);
        const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4")).filter(visible).slice(0, 30).map(h => ({ level: Number(h.tagName.slice(1)), text: clean(h.innerText, 250) })).filter(h => h.text);
        const buttons = Array.from(document.querySelectorAll("button,[role=button]")).filter(visible).slice(0, 40).map(b => clean(b.innerText || b.getAttribute("aria-label") || b.getAttribute("title"), 160)).filter(Boolean);
        const fields = Array.from(document.querySelectorAll("input,textarea,select,[contenteditable=true]")).filter(visible).slice(0, 40).map(el => ({
          type: clean(el.type || el.tagName.toLowerCase(), 30),
          label: clean(el.getAttribute("aria-label") || el.labels?.[0]?.innerText || el.getAttribute("placeholder") || el.getAttribute("name"), 120)
        })).filter(f => f.label && !/password|secret|token|otp|verification|credit.?card|cvv/i.test(f.label + " " + f.type));
        const pageText = redact(document.body?.innerText || "");
        return { title: clean(document.title, 300), url: location.href.slice(0, 2048), headings, buttons, links, fields, selectedText: redact(window.getSelection()?.toString() || "").slice(0, 1000), pageText, capturedAt: new Date().toISOString(), readOnly: true };
      }
    });
    const snapshot = injected?.[0]?.result;
    if (!snapshot?.pageText) throw new Error("Page inspection returned no readable content.");
    await postAgentTaskResult(device, task.task_id, step.step_id, {
      success: true, verified: true,
      receipt: { capability: "browser.inspect_page", ...snapshot, confirmation: "Inspected page structure and visible text (no page interaction or form values)." }
    });
    return;
  }
  if (step.capability === "browser.read_visible_page") {
    const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    if (!tab?.id || !tab.url) throw new Error("There is no active Chrome website to read.");
    const pageUrl = new URL(tab.url);
    if (pageUrl.protocol !== "https:") throw new Error("VOSI can read only HTTPS websites.");
    const hasPermission = await chrome.permissions.contains({ origins: [pageUrl.origin + "/*"] });
    if (!hasPermission) throw new Error("Website access is not enabled. Open the VOSI extension popup and choose Enable current website.");
    const injected = await chrome.scripting.executeScript({
      target: { tabId: tab.id }, world: "ISOLATED",
      func: () => ({
        title: document.title.slice(0, 300),
        url: location.href.slice(0, 2048),
        text: (document.body?.innerText || "").replace(/\s+/g, " ").trim().slice(0, 12000)
      })
    });
    const page = injected?.[0]?.result;
    if (!page?.text) throw new Error("No readable page text was found on the active tab.");
    await postAgentTaskResult(device, task.task_id, step.step_id, {
      success: true, verified: true,
      receipt: { capability: "browser.read_visible_page", title: page.title, url: page.url, text: page.text, character_count: page.text.length, confirmation: "Read page: " + (page.title || page.url) }
    });
    return;
  }
  throw new Error("Unsupported browser capability.");
}

async function executeAvailableAgentTasks() {
  const device = await getPairedDevice();
  if (!device?.deviceToken || !device?.deviceId) return;
  const response = await fetch(API + "/agent/tasks/available", {
    cache: "no-store",
    headers: authHeaders(device)
  });
  if (response.status === 401 || response.status === 403) {
    await chrome.storage.local.set({ vosiConnectionState: "revoked" });
    return;
  }
  if (!response.ok) return;
  const data = await response.json();
  for (const task of (Array.isArray(data.tasks) ? data.tasks : []).slice(0, 3)) {
    if (!["browser.search_products", "browser.open_tab", "browser.read_visible_page", "browser.search_web", "browser.inspect_page", "browser.interact"].includes(task.capability)) continue;
    const claimResponse = await fetch(API + "/agent/tasks/" + encodeURIComponent(task.task_id) + "/claim", {
      method: "POST",
      headers: authHeaders(device),
      cache: "no-store"
    });
    if (!claimResponse.ok) continue;
    const claim = await claimResponse.json();
    const step = claim.step;
    if (!step || !["browser.search_products", "browser.open_tab", "browser.read_visible_page", "browser.search_web", "browser.inspect_page", "browser.interact"].includes(step.capability)) continue;
    if (step.capability !== "browser.search_products") {
      try {
        await executeGeneralBrowserStep(device, task, step);
      } catch (error) {
        await postAgentTaskResult(device, task.task_id, step.step_id, {
          success: false, verified: false, receipt: {}, error: String(error?.message || error).slice(0, 1000)
        }).catch(() => {});
      }
      continue;
    }
    const query = String(step.arguments?.query || "").trim().slice(0, 200);
    if (!query) {
      await fetch(API + "/agent/tasks/" + encodeURIComponent(task.task_id) +
        "/steps/" + encodeURIComponent(step.step_id) + "/result", {
        method: "POST",
        headers: { ...authHeaders(device), "Content-Type": "application/json" },
        body: JSON.stringify({ success: false, verified: false, receipt: {}, error: "Search query is empty." })
      });
      continue;
    }
    const url = "https://www.flipkart.com/search?q=" + encodeURIComponent(query) +
      "&vosi_task_id=" + encodeURIComponent(task.task_id) +
      "&vosi_step_id=" + encodeURIComponent(step.step_id);
    try {
      await chrome.tabs.create({ url, active: true });
    } catch (error) {
      await fetch(API + "/agent/tasks/" + encodeURIComponent(task.task_id) +
        "/steps/" + encodeURIComponent(step.step_id) + "/result", {
        method: "POST",
        headers: { ...authHeaders(device), "Content-Type": "application/json" },
        body: JSON.stringify({ success: false, verified: false, receipt: {}, error: String(error).slice(0, 1000) })
      });
    }
  }
}

async function checkForVosiCommand() {
  if (checking) return;
  checking = true;
  try {
    const device = await getPairedDevice();
    if (!device?.deviceToken) return;
    await executeAvailableAgentTasks();
    const response = await fetch(API + "/browser/command", {
      cache: "no-store",
      headers: authHeaders(device)
    });
    if (!response.ok) return;
    const data = await response.json();
    const command = data.command;
    if (!command?.request_id || !command.query) return;
    const url = "https://www.flipkart.com/search?q=" + encodeURIComponent(command.query) +
      "&vosi_request=" + encodeURIComponent(command.request_id);
    await chrome.tabs.create({ url, active: true });
    await fetch(API + "/browser/ack/" + encodeURIComponent(command.request_id), {
      method: "POST",
      headers: authHeaders(device)
    });
  } catch (error) {
    console.warn("VOSI browser bridge could not reach its local backend:", error);
  } finally {
    checking = false;
  }
}

async function forwardProductResults(message, sender) {
  if (sender.id !== chrome.runtime.id || !sender.url?.startsWith("https://www.flipkart.com/")) {
    throw new Error("Product results were not sent by the VOSI Flipkart content script.");
  }
  const device = await getPairedDevice();
  if (!device?.deviceToken) throw new Error("Pair this Chrome extension with VOSI first.");
  const response = await fetch(API + "/browser/results", {
    method: "POST",
    headers: { ...authHeaders(device), "Content-Type": "application/json" },
    body: JSON.stringify({
      request_id: message.requestId,
      products: Array.isArray(message.products) ? message.products.slice(0, 30) : []
    })
  });
  if (!response.ok) throw new Error("VOSI rejected the product results (" + response.status + ").");
  return response.json();
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "VOSI_DEVICE_UPDATED") {
    void sendHeartbeat();
    void checkForVosiCommand();
    return false;
  }
  if (message?.type === "VOSI_BROWSER_RESULTS") {
    forwardProductResults(message, sender)
      .then(result => sendResponse({ success: true, result }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true;
  }
  if (message?.type === "VOSI_AGENT_BROWSER_RESULTS") {
    reportAgentBrowserResults(message, sender)
      .then(result => sendResponse({ success: true, result }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true;
  }
  return false;
});

function startVosiAlarms() {
  chrome.alarms.create("vosi-poll", { periodInMinutes: 0.5 });
  chrome.alarms.create("vosi-device-heartbeat", { periodInMinutes: 1 });
  void sendHeartbeat();
  void checkForVosiCommand();
}

chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === "vosi-poll") void checkForVosiCommand();
  if (alarm.name === "vosi-device-heartbeat") void sendHeartbeat();
});
chrome.runtime.onInstalled.addListener(startVosiAlarms);
chrome.runtime.onStartup.addListener(startVosiAlarms);
startVosiAlarms();
