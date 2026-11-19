const API = "http://127.0.0.1:8001";
const DEVICE_KEY = "vosiPairedDevice";
const CAPABILITIES = ["browser.search_products", "browser.open_tab", "browser.read_visible_page"];

const pairSection = document.getElementById("pairSection");
const deviceCard = document.getElementById("deviceCard");
const codeInput = document.getElementById("pairingCode");
const pairButton = document.getElementById("pairButton");
const heartbeatButton = document.getElementById("heartbeatButton");
const disconnectButton = document.getElementById("disconnectButton");
const enableSiteButton = document.getElementById("enableSiteButton");
const statusEl = document.getElementById("status");
const deviceLabel = document.getElementById("deviceLabel");
const deviceMeta = document.getElementById("deviceMeta");

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.style.color = isError ? "#ff9a9a" : "#c4c5ce";
}

async function getDevice() {
  const data = await chrome.storage.local.get(DEVICE_KEY);
  return data[DEVICE_KEY] || null;
}

function showDevice(device) {
  pairSection.style.display = device ? "none" : "block";
  deviceCard.style.display = device ? "block" : "none";
  if (device) {
    deviceLabel.textContent = device.label || "Chrome";
    deviceMeta.textContent = "Device ID: " + device.deviceId + "\nCapabilities: " + (device.capabilities || []).join(", ");
  }
}

async function pairChrome() {
  const pairingCode = codeInput.value.trim();
  if (pairingCode.length < 20) {
    setStatus("Paste the complete pairing code from CHERRY AI.", true);
    return;
  }
  pairButton.disabled = true;
  setStatus("Pairing Chrome securely…");
  try {
    const response = await fetch(API + "/agent/devices/pair", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pairing_code: pairingCode, capabilities: CAPABILITIES })
    });
    const data = await response.json();
    if (!response.ok || !data.success || !data.device?.device_token) {
      throw new Error(data.detail || data.error || "Pairing failed. Generate a fresh code in CHERRY AI.");
    }
    const paired = data.device;
    const stored = {
      deviceId: paired.device_id,
      deviceToken: paired.device_token,
      platform: paired.platform,
      label: paired.label,
      capabilities: paired.capabilities,
      pairedAt: paired.paired_at
    };
    await chrome.storage.local.set({ [DEVICE_KEY]: stored });
    codeInput.value = "";
    showDevice(stored);
    setStatus("Chrome is paired. CHERRY AI can now authenticate this browser bridge.");
    chrome.runtime.sendMessage({ type: "CHERRY AI_DEVICE_UPDATED" }).catch(() => {});
  } catch (error) {
    setStatus(error.message || "Could not reach CHERRY AI. Check that the backend is running.", true);
  } finally {
    pairButton.disabled = false;
  }
}

async function checkConnection() {
  const device = await getDevice();
  if (!device) return;
  heartbeatButton.disabled = true;
  setStatus("Checking the CHERRY AI connection…");
  try {
    const response = await fetch(API + "/agent/devices/" + encodeURIComponent(device.deviceId) + "/heartbeat", {
      method: "POST",
      headers: { Authorization: "Bearer " + device.deviceToken }
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "This device credential was rejected.");
    setStatus("Connected to CHERRY AI. Last heartbeat: " + data.device.last_seen_at);
  } catch (error) {
    setStatus(error.message || "CHERRY AI backend is unavailable.", true);
  } finally {
    heartbeatButton.disabled = false;
  }
}

let currentSiteOrigin = null;

async function refreshCurrentSite() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    if (!tab?.url) return;
    const parsed = new URL(tab.url);
    currentSiteOrigin = parsed.protocol === "https:" && parsed.hostname ? parsed.origin : null;
  } catch {
    currentSiteOrigin = null;
  }
}

function enableCurrentSite() {
  if (!currentSiteOrigin) {
    setStatus("Open an HTTPS website in Chrome, then reopen this popup.", true);
    return;
  }
  enableSiteButton.disabled = true;
  // Request permission immediately from the click gesture; do not await other APIs first.
  const permissionRequest = chrome.permissions.request({ origins: [currentSiteOrigin + "/*"] });
  permissionRequest.then(granted => {
    if (!granted) throw new Error("Chrome permission was not granted. CHERRY AI cannot read this website.");
    setStatus("Permission granted for " + currentSiteOrigin + ". CHERRY AI can now read visible page text when you ask.");
  }).catch(error => {
    setStatus(error.message || "Could not enable this website.", true);
  }).finally(() => {
    enableSiteButton.disabled = false;
  });
}

async function disconnectChrome() {
  const device = await getDevice();
  if (!device) return;
  disconnectButton.disabled = true;
  setStatus("Revoking this Chrome device…");
  try {
    const response = await fetch(API + "/agent/devices/me", {
      method: "DELETE",
      headers: { Authorization: "Bearer " + device.deviceToken }
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not revoke the device. It remains saved.");
    await chrome.storage.local.remove(DEVICE_KEY);
    showDevice(null);
    setStatus("Chrome disconnected and its server credential revoked.");
  } catch (error) {
    setStatus(error.message || "Could not reach CHERRY AI to revoke this device.", true);
  } finally {
    disconnectButton.disabled = false;
  }
}

pairButton.addEventListener("click", pairChrome);
heartbeatButton.addEventListener("click", checkConnection);
disconnectButton.addEventListener("click", disconnectChrome);
enableSiteButton.addEventListener("click", enableCurrentSite);

refreshCurrentSite();
getDevice().then(device => {
  showDevice(device);
  if (device) void checkConnection();
}).catch(() => setStatus("Could not read this extension's local pairing state.", true));
