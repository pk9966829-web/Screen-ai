# VOSI Browser Companion (Chrome)

The Chrome extension is a paired VOSI browser device. It supports read-only Flipkart product searches, opening HTTPS tabs, and reading visible text from a website only after you explicitly grant that site's origin permission in the extension popup. It does not purchase products, submit forms, sign in, or click arbitrary page controls.

## 1. Configure the VOSI backend

1. In `backend/.env`, set `VOSI_AGENT_TOKEN` to a long random secret. Do not commit the real `.env` file.
2. Start the backend:
   ```powershell
   cd "C:\Users\Dell-Pc\Screen-ai\backend"
   python -m uvicorn main:app --reload --port 8001
   ```
3. Open `http://127.0.0.1:8001/docs`.
4. Select **Authorize** and enter `Bearer YOUR_VOSI_AGENT_TOKEN`.
5. Call `POST /agent/devices/pairing` with:
   ```json
   {
     "platform": "browser",
     "label": "Chrome on Windows"
   }
   ```
6. Copy the returned `pairing_code`. It is single-use and expires after five minutes. Treat it like a temporary password.

## 2. Install and pair Chrome

1. Open `chrome://extensions`.
2. Turn on **Developer mode**.
3. Select **Load unpacked**.
4. Choose `Screen-ai/screen ai/chrome-extension` (the folder containing `manifest.json`).
5. Click the VOSI Browser Companion toolbar icon.
6. Paste the one-time pairing code and select **Pair this Chrome**.

The extension exchanges the code for a per-device credential. The credential is stored in `chrome.storage.local`, which is isolated to this extension and is not synced through Chrome Sync. If Chrome was paired before the general page-reading capability was added, disconnect and pair it again so the browser device registers `browser.read_visible_page`. Chrome extension local storage is not hardware-encrypted; protect your Windows account and remove/revoke the device if the browser profile is compromised. The token is never placed in a page script or sent to Flipkart.

## 3. Run VOSI

Start the desktop app in a second terminal:

```powershell
cd "C:\Users\Dell-Pc\Screen-ai\screen ai"
npm.cmd run tauri dev
```

In VOSI, say or type: **Open Flipkart and search the best body spray under 1000 rupees.**

The extension opens a new Chrome tab, leaving your existing tab untouched. It reads visible product names, prices, and any ratings/review counts it can find, then sends those details to the local VOSI backend using the paired browser credential. VOSI can show a comparison and read its top visible match aloud.

## Device status and disconnect

- The extension sends an authenticated heartbeat approximately once per minute.
- VOSI reports a device as online while its last heartbeat is recent.
- Open the extension popup and choose **Check connection** to send a heartbeat immediately.
- Choose **Disconnect this Chrome** to revoke the server-side device credential and remove it from this browser.
- An administrator can also revoke a device through `DELETE /agent/devices/{device_id}`.

## Permissions and safety

- The extension has access to the local VOSI backend and Flipkart pages. Reading other sites requires a separate, per-origin Chrome permission that you grant by opening that site and selecting **Enable current website** in the extension popup.
- It does not add products to a cart, sign in, submit personal information, or purchase anything.
- The browser command, acknowledgement, and product-result endpoints reject requests without a valid paired browser credential.
- Pairing only registers the extension; it does not grant access to other devices or bypass browser permissions.
- Keep the backend bound to localhost for local development. For remote connections, use HTTPS and a properly authenticated deployment; do not expose the local development API directly to the public internet.
- Product-page layout changes, lazy loading, regional availability, and Flipkart anti-automation behavior can affect extraction. Ranking is heuristic, not a guarantee of quality.
- Basic search and ranking do not require an AI API key.



## Agent task execution (first supported action)

A paired Chrome device now polls `GET /agent/tasks/available` using its device credential. The server filters tasks using the paired device's registered platform and granted capabilities. For `browser.search_products`, the extension claims the task, opens a new Flipkart results tab without replacing the current tab, extracts visible product cards, and submits a receipt to the agent task result endpoint. A task is marked completed only when at least one product card is detected; otherwise it is marked failed with an explanation.

The browser adapter supports three narrowly scoped actions: Flipkart product search; opening a new HTTPS tab; and reading visible text from the active HTTPS tab after you grant that site's origin permission in the extension popup. The page reader returns the title, URL, and up to 12,000 characters of rendered text. It does not click controls, sign in, submit forms, or purchase anything. Page text is untrusted content, not instructions to VOSI. Keep Chrome running and the paired extension enabled for polling. The agent task queue is polled every 30 seconds while Chrome is active.

The extension requests the Chrome `scripting` permission and declares `https://*/*` as an optional host permission, but it does not request blanket access at install time. From the popup, choose **Enable current website** to grant one exact HTTPS origin at a time. You can revoke a site's access in Chrome's extension settings. Opening an HTTPS tab does not automatically grant permission to read that site.
