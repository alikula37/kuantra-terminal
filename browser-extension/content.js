/**
 * Kuantra Terminal - TradingView Content Script
 * Observes DOM mutations and title changes to detect active symbol & timeframe in real-time.
 */

let lastSyncedSymbol = "";
let lastSyncedInterval = "";

function extractSymbolAndTimeframe() {
  // Strategy 1: Read TradingView document title (e.g. "BTCUSDT 64,820.00 — 15 — Binance")
  const title = document.title || "";
  const titleParts = title.split("—").map(s => s.trim());
  
  let symbol = "";
  let timeframe = "15m";
  let exchange = "BINANCE";

  if (titleParts.length >= 2) {
    const firstPart = titleParts[0].split(" ")[0].trim();
    if (firstPart) symbol = firstPart;
    if (titleParts.length >= 3) {
      timeframe = titleParts[1] || "15m";
      exchange = titleParts[2] || "BINANCE";
    }
  }

  // Strategy 2: Check header DOM elements if title is generic
  if (!symbol || symbol.includes("TradingView")) {
    const symbolBtn = document.querySelector("#header-toolbar-symbol-search") || 
                      document.querySelector("[data-name='legend-series-item']");
    if (symbolBtn && symbolBtn.textContent) {
      symbol = symbolBtn.textContent.trim().split(" ")[0];
    }
  }

  // Strategy 3: Check Interval toolbar button
  const intervalBtn = document.querySelector("#header-toolbar-intervals [aria-checked='true']") ||
                      document.querySelector("#header-toolbar-intervals div");
  if (intervalBtn && intervalBtn.textContent) {
    timeframe = intervalBtn.textContent.trim();
  }

  if (symbol && (symbol !== lastSyncedSymbol || timeframe !== lastSyncedInterval)) {
    lastSyncedSymbol = symbol;
    lastSyncedInterval = timeframe;

    const payload = {
      type: "TV_SYMBOL_CHANGE",
      symbol: symbol.replace(/[^a-zA-Z0-9]/g, "").toUpperCase(),
      timeframe: timeframe,
      exchange: exchange.toUpperCase(),
      timestamp: Date.now()
    };

    chrome.runtime.sendMessage(payload);
    console.log("[Kuantra TV Sync] Emitted symbol change:", payload);
  }
}

// Observe DOM mutations for zero-latency symbol changes
const observer = new MutationObserver(() => {
  extractSymbolAndTimeframe();
});

observer.observe(document.querySelector("head > title") || document.body, {
  subtree: true,
  childList: true,
  characterData: true
});

// Periodic fallback scan (every 500ms)
setInterval(extractSymbolAndTimeframe, 500);
extractSymbolAndTimeframe();