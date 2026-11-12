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

async function executeGeneralBrowserStep(device, task, step) {
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
    if (!["browser.search_products", "browser.open_tab", "browser.read_visible_page"].includes(task.capability)) continue;
    const claimResponse = await fetch(API + "/agent/tasks/" + encodeURIComponent(task.task_id) + "/claim", {
      method: "POST",
      headers: authHeaders(device),
      cache: "no-store"
    });
    if (!claimResponse.ok) continue;
    const claim = await claimResponse.json();
    const step = claim.step;
    if (!step || !["browser.search_products", "browser.open_tab", "browser.read_visible_page"].includes(step.capability)) continue;
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
