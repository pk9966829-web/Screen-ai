"""Standalone, ephemeral Playwright executor for VOSI public Flipkart search tasks.

This worker intentionally supports one read-only workflow. It never signs in,
clicks purchase/checkout controls, submits forms, or handles payment data.
"""
from __future__ import annotations

import logging
import os
import re
import signal
import threading
import time
from typing import Any
from urllib.parse import quote_plus

import requests

LOG = logging.getLogger("vosi-cloud-browser-worker")
STOP = threading.Event()
PRICE_RE = re.compile(r"₹\s?[\d,]+")
RATING_RE = re.compile(r"([0-5](?:\.[0-9])?)\s*★")
REVIEWS_RE = re.compile(r"([\d,]+)\s*(?:Ratings|Reviews)", re.IGNORECASE)
MAX_QUERY_LENGTH = 200
MAX_PRODUCTS = 8
SUPPORTED_HOST = "www.flipkart.com"


class WorkerError(RuntimeError):
    pass


def validate_search_query(arguments: Any) -> str:
    if not isinstance(arguments, dict):
        raise WorkerError("Search arguments must be an object.")
    query = str(arguments.get("query") or "").strip()
    if not query or len(query) > MAX_QUERY_LENGTH:
        raise WorkerError("Search query must contain 1 to 200 characters.")
    if any(ord(char) < 32 for char in query):
        raise WorkerError("Search query contains unsupported control characters.")
    return query


def build_search_url(query: str) -> str:
    # The host and route are fixed; task data can supply only the encoded query.
    return f"https://{SUPPORTED_HOST}/search?q={quote_plus(query)}"


def parse_product_card(text: str, name: str, url: str | None) -> dict[str, Any] | None:
    clean_text = re.sub(r"\s+", " ", text or "").strip()
    clean_name = re.sub(r"\s+", " ", name or "").strip()
    price = PRICE_RE.search(clean_text)
    if not clean_name or len(clean_name) < 4 or not price:
        return None
    rating = RATING_RE.search(clean_text)
    reviews = REVIEWS_RE.search(clean_text)
    safe_url = None
    if url:
        # Do not return links to arbitrary hosts from merchant-controlled markup.
        from urllib.parse import urlsplit
        parsed = urlsplit(url)
        if parsed.scheme == "https" and parsed.hostname in {SUPPORTED_HOST, "flipkart.com"}:
            safe_url = url[:500]
    return {
        "name": clean_name[:120],
        "price": price.group(0),
        "rating": rating.group(1) if rating else None,
        "reviews": reviews.group(1) if reviews else None,
        "url": safe_url,
    }


def extract_products(page: Any) -> list[dict[str, Any]]:
    selectors = "div[data-id], a[href*='/p/'], a[href*='/product/']"
    products: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in page.locator(selectors).all()[:120]:
        try:
            card = node
            if node.evaluate("(el) => el.tagName.toLowerCase() === 'a'"):
                parent = node.locator("xpath=ancestor::div[@data-id][1]")
                if parent.count():
                    card = parent.first
            text = card.inner_text(timeout=1500)
            name_locator = card.locator("a[title], img[alt], .KzDlHZ, .s1Q9rs, .WKTcLC").first
            name = ""
            if name_locator.count():
                name = (
                    name_locator.get_attribute("title")
                    or name_locator.get_attribute("alt")
                    or name_locator.inner_text(timeout=1000)
                )
            if not name:
                first_link = card.locator("a[href]").first
                if first_link.count():
                    name = first_link.inner_text(timeout=1000)
            link = None
            link_locator = card.locator("a[href]").first
            if link_locator.count():
                href = link_locator.get_attribute("href")
                if href:
                    link = href if href.startswith("https://") else f"https://{SUPPORTED_HOST}{href}"
            product = parse_product_card(text, name, link)
            if product and product["name"].casefold() not in seen:
                seen.add(product["name"].casefold())
                products.append(product)
                if len(products) >= MAX_PRODUCTS:
                    break
        except Exception:
            # A malformed/virtualized card should not abort the whole read-only search.
            continue
    return products


class VosiCloudBrowserWorker:
    def __init__(self, base_url: str, token: str, worker_id: str, poll_seconds: float = 4.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.worker_id = worker_id
        self.poll_seconds = max(1.0, min(poll_seconds, 30.0))
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "VOSI-Cloud-Browser-Worker/1.0",
        })

    def _post(self, path: str, payload: dict[str, Any] | None = None, timeout: int = 20):
        response = self.session.post(self.base_url + path, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()

    def _heartbeat_loop(self, task_id: str, step_id: str, interval: int):
        while not STOP.wait(max(10, interval // 3)):
            try:
                self._post(
                    f"/cloud-worker/{task_id}/steps/{step_id}/heartbeat",
                    {}, timeout=10,
                )
            except Exception as exc:
                LOG.warning("Lease heartbeat failed for task %s: %s", task_id[:8], type(exc).__name__)
                return

    def _execute_search(self, query: str, lease_seconds: int) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright

        url = build_search_url(query)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    locale="en-IN",
                    timezone_id="Asia/Kolkata",
                    viewport={"width": 1365, "height": 900},
                    java_script_enabled=True,
                    accept_downloads=False,
                )
                page = context.new_page()
                page.set_default_timeout(8000)
                response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                if response and response.status >= 400:
                    raise WorkerError(f"Flipkart returned HTTP {response.status}.")
                try:
                    page.locator("div[data-id], a[href*='/p/'], a[href*='/product/']").first.wait_for(timeout=20000)
                except Exception:
                    pass
                title = (page.title() or "")[:250]
                page_text = (page.locator("body").inner_text(timeout=5000) or "")[:5000]
                lowered = (title + " " + page_text[:1200]).casefold()
                if any(term in lowered for term in ("captcha", "verify you are human", "access denied", "robot check")):
                    raise WorkerError("The website requested a human verification; VOSI stopped without attempting to bypass it.")
                products = extract_products(page)
                if not products:
                    raise WorkerError("No public product cards could be verified. The page may have changed or blocked automated access.")
                return {
                    "capability": "browser.search_products",
                    "site": "Flipkart",
                    "query": query,
                    "page_title": title,
                    "page_url": page.url,
                    "products": products,
                    "product_count": len(products),
                    "read_only": True,
                    "confirmation": f"Read {len(products)} public Flipkart product listings.",
                }
            finally:
                browser.close()

    def process_claim(self, claim: dict[str, Any]) -> None:
        task = claim.get("task") or {}
        step = claim.get("step") or {}
        task_id, step_id = task.get("task_id"), step.get("step_id")
        if not task_id or not step_id:
            raise WorkerError("Claim response did not contain task and step IDs.")
        heartbeat_stop = threading.Event()
        global STOP
        previous_stop = STOP
        STOP = heartbeat_stop
        heartbeat = threading.Thread(
            target=self._heartbeat_loop,
            args=(task_id, step_id, int(claim.get("lease_seconds") or 180)),
            daemon=True,
        )
        heartbeat.start()
        try:
            if step.get("capability") != "browser.search_products":
                raise WorkerError("This cloud browser worker only supports browser.search_products.")
            query = validate_search_query(step.get("arguments"))
            receipt = self._execute_search(query, int(claim.get("lease_seconds") or 180))
            self._post(
                f"/cloud-worker/{task_id}/steps/{step_id}/result",
                {"success": True, "verified": True, "receipt": receipt},
            )
            LOG.info("Completed read-only search task %s (%s products)", task_id[:8], receipt["product_count"])
        except Exception as exc:
            try:
                self._post(
                    f"/cloud-worker/{task_id}/steps/{step_id}/result",
                    {"success": False, "verified": False, "receipt": {}, "error": str(exc)[:1500]},
                )
            except Exception as report_exc:
                LOG.error("Could not report task failure %s: %s", task_id[:8], type(report_exc).__name__)
            LOG.warning("Task %s stopped: %s", task_id[:8], str(exc)[:300])
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=2)
            STOP = previous_stop

    def run_forever(self) -> None:
        health = self.session.get(self.base_url + "/cloud-worker/health", timeout=15)
        health.raise_for_status()
        details = health.json()
        if "browser.search_products" not in details.get("capabilities", []):
            raise WorkerError("Server has not granted browser.search_products to this worker.")
        LOG.info("VOSI cloud browser worker %s connected; capabilities=%s", self.worker_id, details["capabilities"])
        while not STOP.is_set():
            try:
                claim = self._post("/cloud-worker/claim", {}, timeout=20)
                if claim.get("task") and claim.get("step"):
                    self.process_claim(claim)
                else:
                    STOP.wait(self.poll_seconds)
            except requests.RequestException as exc:
                LOG.warning("VOSI API temporarily unavailable: %s", type(exc).__name__)
                STOP.wait(self.poll_seconds)
            except Exception:
                LOG.exception("Worker loop error")
                STOP.wait(self.poll_seconds)


def main() -> None:
    logging.basicConfig(
        level=os.getenv("VOSI_WORKER_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    base_url = os.getenv("VOSI_CLOUD_API_URL", "").strip()
    token = os.getenv("VOSI_CLOUD_WORKER_TOKEN", "").strip()
    worker_id = os.getenv("VOSI_CLOUD_WORKER_ID", "browser-worker-1").strip()
    if not base_url or not token:
        raise SystemExit("Set VOSI_CLOUD_API_URL and VOSI_CLOUD_WORKER_TOKEN.")
    if not base_url.startswith("https://"):
        raise SystemExit("VOSI_CLOUD_API_URL must use HTTPS.")
    worker = VosiCloudBrowserWorker(base_url, token, worker_id)
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())
    signal.signal(signal.SIGINT, lambda *_: STOP.set())
    worker.run_forever()


if __name__ == "__main__":
    main()
