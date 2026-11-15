# VOSI Flipkart Chrome Bridge

This extension connects the VOSI desktop app to the user's Chrome browser for read-only Flipkart product searches.

## Install once

1. Pull the latest `feature/gmail-connectors` branch of the VOSI repository.
2. Open Chrome and visit `chrome://extensions`.
3. Turn on **Developer mode**.
4. Choose **Load unpacked**.
5. Select the folder `Screen-ai/screen ai/chrome-extension` (the folder containing `manifest.json`).
6. Keep the extension enabled.

## Run VOSI

1. Start the FastAPI backend in one terminal:
   ```powershell
   cd "C:\Users\Dell-Pc\Screen-ai\backend"
   python -m uvicorn main:app --reload --port 8001
   ```
2. Start the VOSI desktop app in another terminal:
   ```powershell
   cd "C:\Users\Dell-Pc\Screen-ai\screen ai"
   npm.cmd run tauri dev
   ```
3. In VOSI, say or type: **Open Flipkart and search the best body spray under 1000 rupees.**

The extension opens a new Chrome tab, leaving the existing tab untouched. It reads visible product names, prices, and any ratings/review counts it can find, then sends those details to the local VOSI backend. VOSI shows a short comparison and reads its top visible match aloud.

## Notes

- The extension only has access to Flipkart pages and the local VOSI backend.
- It does not add products to a cart, sign in, submit personal information, or purchase anything.
- Product-page layout changes, lazy loading, regional availability, and Flipkart anti-automation behavior can affect extraction. The ranking is a heuristic based on visible prices, ratings, and review counts, not a guarantee of quality.
- Basic search and ranking do not require an AI API key.
- The extension checks for new VOSI requests every 30 seconds. Keep Chrome and the backend running while testing.
