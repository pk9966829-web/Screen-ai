(() => {
  const params = new URLSearchParams(location.search);
  const requestId = params.get("vosi_request");
  if (!requestId || !location.pathname.includes("/search")) return;

  const clean = value => (value || "").replace(/\\s+/g, " ").trim();
  const pricePattern = /₹\\s?[\\d,]+/;
  const sent = new Set();

  function collect() {
    const candidates = Array.from(document.querySelectorAll("div[data-id], a[href*='/p/'], a[href*='/product/']"));
    const products = [];
    for (const node of candidates) {
      const card = node.matches("a") ? node.closest("div[data-id]") || node : node;
      const text = clean(card.innerText || card.textContent);
      const nameNode = card.querySelector("a[title], img[alt], .KzDlHZ, .s1Q9rs, .WKTcLC");
      const name = clean(nameNode?.getAttribute("title") || nameNode?.getAttribute("alt") || nameNode?.textContent || card.querySelector("a")?.innerText);
      const priceMatch = text.match(pricePattern);
      if (!name || !priceMatch || name.length < 4 || products.some(p => p.name === name)) continue;
      const ratingMatch = text.match(/([0-5](?:\\.[0-9])?)\\s*★/);
      const reviewsMatch = text.match(/([\\d,]+)\\s*(?:Ratings|Reviews)/i);
      const link = card.matches("a") ? card.href : card.querySelector("a[href]")?.href;
      products.push({
        name: name.slice(0, 180),
        price: priceMatch[0],
        rating: ratingMatch ? ratingMatch[1] : null,
        reviews: reviewsMatch ? reviewsMatch[1] : null,
        url: link || null
      });
      if (products.length >= 20) break;
    }
    return products;
  }

  let attempts = 0;
  const timer = setInterval(async () => {
    attempts += 1;
    const products = collect();
    if (!products.length && attempts < 15) return;
    clearInterval(timer);
    if (sent.has(requestId)) return;
    sent.add(requestId);
    try {
      await fetch("http://127.0.0.1:8001/browser/results", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request_id: requestId, products })
      });
    } catch (error) {
      console.warn("VOSI could not send Flipkart listings to its local backend:", error);
    }
  }, 1500);
})();