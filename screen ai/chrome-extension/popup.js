const API = "http://127.0.0.1:8001";
const DEVICE_KEY = "vosiPairedDevice";
const CAPABILITIES = ["browser.search_products", "browser.open_tab"];

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
    setStatus("Paste the complete pairing code from VOSI.", true);
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
      throw new Error(data.detail || data.error || "Pairing failed. Generate a fresh code in VOSI.");
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
    setStatus("Chrome is paired. VOSI can now authenticate this browser bridge.");
    chrome.runtime.sendMessage({ type: "VOSI_DEVICE_UPDATED" }).catch(() => {});
  } catch (error) {
    setStatus(error.message || "Could not reach VOSI. Check that the backend is running.", true);
  } finally {
    pairButton.disabled = false;
  }
}

async function checkConnection() {
  const device = await getDevice();
  if (!device) return;
  heartbeatButton.disabled = true;
  setStatus("Checking the VOSI connection…");
  try {
    const response = await fetch(API + "/agent/devices/" + encodeURIComponent(device.deviceId) + "/heartbeat", {
      method: "POST",
      headers: { Authorization: "Bearer " + device.deviceToken }
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "This device credential was rejected.");
    setStatus("Connected to VOSI. Last heartbeat: " + data.device.last_seen_at);
  } catch (error) {
    setStatus(error.message || "VOSI backend is unavailable.", true);
  } finally {
    heartbeatButton.disabled = false;
  }
}

async function enableCurrentSite() {
  const device = await getDevice();
  if (!device) return;
  enableSiteButton.disabled = true;
  try {
    const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    if (!tab?.url) throw new Error("Open the website you want VOSI to read, then try again.");
    const parsed = new URL(tab.url);
    if (parsed.protocol !== "https:" || !parsed.hostname) throw new Error("VOSI can read only HTTPS websites, not browser-internal or local pages.");
    const granted = await chrome.permissions.request({ origins: [parsed.origin + "/*"] });
    if (!granted) throw new Error("Chrome permission was not granted. VOSI cannot read this website.");
    setStatus("Permission granted for " + parsed.origin + ". VOSI can now read visible page text when you ask.");
  } catch (error) {
    setStatus(error.message || "Could not enable this website.", true);
  } finally {
    enableSiteButton.disabled = false;
  }
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
    setStatus(error.message || "Could not reach VOSI to revoke this device.", true);
  } finally {
    disconnectButton.disabled = false;
  }
}

pairButton.addEventListener("click", pairChrome);
heartbeatButton.addEventListener("click", checkConnection);
disconnectButton.addEventListener("click", disconnectChrome);
enableSiteButton.addEventListener("click", enableCurrentSite);

getDevice().then(device => {
  showDevice(device);
  if (device) void checkConnection();
}).catch(() => setStatus("Could not read this extension's local pairing state.", true));
