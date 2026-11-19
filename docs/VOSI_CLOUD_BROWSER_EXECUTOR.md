# VOSI Cloud Browser Executor

## Scope of this first executor

This is the first real cloud browser worker, not just a queue API. It runs as a separate process/container and claims tasks from the authenticated VOSI cloud-worker API. Its first supported action is **read-only public Flipkart product search**.

It:
- Opens a fresh, ephemeral headless Chromium context for each search.
- Uses only the task's text query; the destination host and search route are fixed in code.
- Restricts browser network requests to HTTPS Flipkart and Flixcart hosts.
- Extracts up to eight visible product names, listed prices, displayed ratings/review counts, and same-site links.
- Sends a verified receipt to VOSI only after it has parsed actual product cards.
- Renews its task lease while the browser is working.
- Stops if the site redirects off the supported host or presents a human-verification/access-denied page.

It does **not** sign in, import cookies, use stored merchant sessions, click arbitrary page controls, submit forms, add items to a cart, place orders, or process payment details. Website text is treated as untrusted content, never as instructions for the worker.

## Deployment

Deploy the API first using the instructions in [VOSI Cloud Execution Engine](VOSI_CLOUD_EXECUTION_ENGINE.md). It must use an always-on host, HTTPS, a persistent disk, and one API instance with the current SQLite runtime.

On the API service, configure:

```env
VOSI_CLOUD_WORKER_TOKEN=<a separate long random secret>
VOSI_CLOUD_WORKER_ID=browser-worker-1
VOSI_CLOUD_WORKER_PLATFORM=browser
VOSI_CLOUD_WORKER_CAPABILITIES=browser.search_products
VOSI_CLOUD_WORKER_LEASE_SECONDS=180
```

Build the worker image from the repository root:

```sh
docker build -f backend/Dockerfile.browser-worker -t vosi-cloud-browser-worker ./backend
```

Run it as a separate always-on worker service:

```sh
docker run --rm \
  -e VOSI_CLOUD_API_URL=https://<your-vosi-api-host> \
  -e VOSI_CLOUD_WORKER_TOKEN=<same-worker-secret> \
  -e VOSI_CLOUD_WORKER_ID=browser-worker-1 \
  vosi-cloud-browser-worker
```

The API and worker must use the same worker token and worker ID. The worker refuses a non-HTTPS API URL and verifies its identity and granted capability at startup. Store secrets in the hosting provider's secret manager; do not commit them or bake them into the image.

## Local smoke test

After starting the API with the environment above, the worker can be run locally from the backend directory after installing the worker requirements and Playwright Chromium:

```sh
pip install -r cloud-browser-worker-requirements.txt
playwright install chromium
set VOSI_CLOUD_API_URL=https://<your-vosi-api-host>
set VOSI_CLOUD_WORKER_TOKEN=<same-worker-secret>
set VOSI_CLOUD_WORKER_ID=browser-worker-1
python cloud_browser_worker.py
```

Do not use a public internet-facing API without HTTPS and strong secrets. For local development, use a private tunnel with HTTPS rather than exposing an unauthenticated local port.

## Task flow

1. Android/desktop VOSI creates a scheduled or immediate `browser.search_products` task.
2. The cloud API waits until the scheduled time, then leases the task to the configured browser worker.
3. The worker validates the query, opens the fixed Flipkart search URL, reads visible listings, and reports a receipt.
4. VOSI marks the step complete only after the API accepts a successful, verified receipt.
5. The Android companion can later display task progress/results through the companion task and notification experience.

## Current deployment and product limits

- The worker code and container are committed, but **not deployed** by this repository change. A hosting account, secrets, persistent database storage, and an always-on worker service still need to be configured.
- The API's SQLite runtime remains single-instance; do not horizontally scale it. PostgreSQL migration is required before multiple API replicas.
- Flipkart can change its page structure, rate-limit automation, or require a human challenge. The worker stops rather than bypassing a challenge.
- This first adapter does not support other merchants yet. Each additional site needs its own reviewed, allowlisted, read-only adapter and tests.
- No Zomato/Swiggy cart, checkout, or order placement is implemented here. A later commerce adapter must preserve the exact checkout summary and originating-device approval contract.
- No physical phone, merchant account, or live cloud deployment test is claimed.

## Android app commitment

The Android app remains a core VOSI deliverable. See [VOSI Android App Roadmap](VOSI_ANDROID_APP_ROADMAP.md). The next dedicated milestone after this worker is the polished native Android companion experience, followed by cloud push notifications and a phone-based approval centre. The phone is the user's control/approval surface; it does not need to stay awake to keep the cloud worker running once the cloud services are deployed.
