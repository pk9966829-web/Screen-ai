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

async function checkForVosiCommand() {
  if (checking) return;
  checking = true;
  try {
    const device = await getPairedDevice();
    if (!device?.deviceToken) return;
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
    // Open a new Chrome tab so the user's current page is left untouched.
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
