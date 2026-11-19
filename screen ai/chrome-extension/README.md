# VOSI Browser Companion (Chrome)

The Chrome extension is a paired VOSI browser device. It connects the browser to the shared VOSI agent runtime and can execute only the capabilities granted to that paired device.

## Supported browser capabilities

- Search public Flipkart product listings and extract visible product names, prices, ratings, and review counts where available.
- Open a new HTTPS tab without replacing the user's current tab.
- Inspect the active HTTPS page and read visible text after the user grants permission for that exact origin.
- Perform bounded **click**, **type**, **scroll**, and **select** actions on visible, labelled controls after explicit per-origin permission.

The interaction adapter is intentionally limited. It blocks sensitive fields, sign-in and authorization controls, form submission, and controls likely to purchase, pay, send, delete, transfer, book, or otherwise create consequential effects. A click receipt means the click was dispatched; it is not proof that the website completed the requested operation. VOSI must inspect the resulting page state before reporting a verified outcome.

## 1. Configure the VOSI backend

1. In `backend/.env`, set `VOSI_AGENT_TOKEN` to a long random secret. Never commit the real `.env` file.
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

The extension exchanges the code for a per-device credential stored in `chrome.storage.local`. It is isolated to this extension and is not synced through Chrome Sync. Chrome extension local storage is not hardware-encrypted; protect your Windows account and revoke the device if the browser profile is compromised. The token is never placed in a page script or sent to websites.

## 3. Grant access to a website

The extension requests `scripting` and optional HTTPS host permissions, not blanket access to every site at install time.

1. Open the website in Chrome.
2. Open the VOSI Browser Companion popup.
3. Choose **Enable current website**.
4. Review Chrome's permission prompt and grant access only if you trust the site.

Each origin must be granted separately. Opening an HTTPS tab does not automatically grant permission to read or interact with it. You can revoke an origin's access in Chrome's extension settings.

## 4. Run VOSI

Start the VOSI backend and Windows desktop app:

```powershell
cd "C:\Users\Dell-Pc\Screen-ai\screen ai"
npm.cmd run tauri dev
```

With Chrome paired and running, ask VOSI: **Open Flipkart and search for the best body spray under 1000 rupees.**

The extension opens a new results tab, extracts visible product details, and returns a receipt to the backend. The companion can compare the returned products and optionally speak a heuristic top-three recommendation. Product ranking depends on the page content, region, stock, and layout; it is not a guarantee of product quality.

For another site, first grant that site's origin permission as described above. VOSI can then inspect the active page and use the bounded interaction actions on supported, visible controls. It will not submit a form or complete a purchase.

## Android Companion handoff

A paired Android Companion can request supported tasks through the shared VOSI backend. The task is executed by a matching online device with the required capability. For browser tasks, Chrome must remain open with the VOSI extension paired and polling. The phone does not gain arbitrary access to the browser merely by being paired.

## Device status and disconnect

- The extension sends an authenticated heartbeat approximately once per minute.
- Open the extension popup and choose **Check connection** to send a heartbeat immediately.
- Choose **Disconnect this Chrome** to revoke the server-side device credential and remove it from this browser.
- An administrator can revoke a device through `DELETE /agent/devices/{device_id}`.

## Security and operational boundaries

- Browser commands, task claims, and result receipts require a valid paired browser credential.
- The server checks the paired device's registered platform and capabilities before offering work.
- Website content is untrusted data, never instructions to VOSI.
- No sign-in, CAPTCHA bypass, sensitive-field entry, form submission, payment, purchase, or other consequential website action is supported by this adapter.
- Keep the backend bound to localhost for local development. For remote connections, use HTTPS and a properly authenticated deployment; never expose the local development API directly to the public internet.
- Product-page layout changes, lazy loading, regional availability, and anti-automation behavior can affect extraction.
- The optional cloud browser worker is a separate, read-only Flipkart product-search adapter; it is not a general-purpose browser interaction worker.
