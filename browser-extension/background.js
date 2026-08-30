/**
 * Kuantra Terminal - Service Worker & Local WS Bridge
 * Maintains persistent WebSocket connection to Kuantra C++ Sidecar ws://127.0.0.1:8000/ws/tv-sync
 */

let ws = null;
let isConnected = false;
let currentSymbol = "BTCUSDT";
let currentInterval = "15m";

function connectWebSocket() {
  try {
    ws = new WebSocket("ws://127.0.0.1:8000/ws/tv-sync");

    ws.onopen = () => {
      isConnected = true;
      console.log("[Kuantra TV Sync] Bridge connected to Kuantra Terminal Sidecar!");
      chrome.storage.local.set({ isConnected: true });
    };

    ws.onmessage = (event) => {
      console.log("[Kuantra TV Sync] Message from terminal:", event.data);
    };

    ws.onclose = () => {
      isConnected = false;
      chrome.storage.local.set({ isConnected: false });
      setTimeout(connectWebSocket, 2000); // Reconnect loop
    };

    ws.onerror = (err) => {
      isConnected = false;
      chrome.storage.local.set({ isConnected: false });
      ws.close();
    };
  } catch (e) {
    isConnected = false;
    setTimeout(connectWebSocket, 2000);
  }
}

connectWebSocket();

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "TV_SYMBOL_CHANGE") {
    currentSymbol = message.symbol;
    currentInterval = message.timeframe;

    chrome.storage.local.set({
      activeSymbol: currentSymbol,
      activeInterval: currentInterval,
      lastSyncTime: Date.now()
    });

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        event: "TV_SYNC",
        symbol: message.symbol,
        timeframe: message.timeframe,
        exchange: message.exchange,
        source: "browser_extension",
        timestamp: message.timestamp
      }));
      console.log("[Kuantra TV Sync] Forwarded to Kuantra Sidecar:", message.symbol);
    }
    sendResponse({ status: "SENT", symbol: message.symbol });
  }
  return true;
});