# VOSI read-only cloud browser worker

The cloud browser worker executes one deliberately narrow workflow: read public Flipkart product listings for a user's query. It does not log in, bypass human verification, click purchase controls, submit forms, or handle checkout/payment data.

## Run with Docker Compose

The worker is an optional Compose profile. Configure these values in `.env`:

- `VOSI_CLOUD_WORKER_TOKEN`: a long random worker secret; must match the API configuration.
- `VOSI_CLOUD_WORKER_ID`: for example `browser-worker-1`; must match the API configuration.
- `VOSI_CLOUD_WORKER_PLATFORM=browser`
- `VOSI_CLOUD_WORKER_CAPABILITIES=browser.search_products`
- `VOSI_CLOUD_WORKER_ACCOUNT_TOKEN`: a valid VOSI account session for the account whose tasks this worker should execute. Required when `VOSI_MULTI_TENANT=true`. Treat it as a password; never commit it or put it in logs.
- `VOSI_CLOUD_API_URL=https://api.your-domain.example`

Then run:

```bash
docker compose --profile cloud-worker up -d --build cloud-browser-worker
```

The worker uses the account token on health, claim, heartbeat and result requests. In multi-tenant mode, the API returns only that account's tasks and rejects heartbeats or receipts for another account's task. Deploy a separate worker instance and account session for each account that needs cloud execution; do not share account sessions.

## Local development

Install `cloud-browser-worker-requirements.txt`, install the Playwright Chromium browser, configure the environment above, and run:

```bash
python cloud_browser_worker.py
```

The worker requires outbound HTTPS to the VOSI API and Flipkart's allowed domains. If Flipkart presents a CAPTCHA or human-verification page, the worker stops and reports a failure instead of attempting to bypass it.

## Operational boundary

This worker is not a general-purpose browser agent. It handles public product search only. Other browser tasks remain assigned to the user's paired Chrome extension until a separately reviewed adapter is added. It must run with an account-scoped session in hosted multi-tenant mode.
