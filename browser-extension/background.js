/**
 * Kuantra Terminal - Service Worker & Local WS Bridge
 *
 * Maintains a persistent WebSocket connection to the Kuantra Terminal desktop app's
 * integrations gateway: ws://127.0.0.1:<bridgePort>/ws/tv-sync
 *
 * The desktop app runs as a single process; the gateway is the only socket it exposes
 * and it listens on 127.0.0.1:8765 by default. The port is configurable from the popup
 * and is persisted in chrome.storage.local under `bridgePort`.
 */

const DEFAULT_BRIDGE_PORT = 8765;

let ws = null;
let isConnected = false;
let currentSymbol = "BTCUSDT";
let currentInterval = "15m";
let activePort = DEFAULT_BRIDGE_PORT;
let reconnectTimer = null;

function normalizePort(value) {
  const port = parseInt(value, 10);
  if (!Number.isFinite(port) || port < 1024 || port > 65535) return DEFAULT_BRIDGE_PORT;
  return port;
}

function scheduleReconnect(delay = 2000) {
  if (reconnectTimer !== null) clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectWebSocket();
  }, delay);
}

function closeSocket() {
  if (!ws) return;
  const stale = ws;
  ws = null;
  stale.onopen = null;
  stale.onmessage = null;
  stale.onclose = null;
  stale.onerror = null;
  try {
    stale.close();
  } catch (e) {
    /* already closed */
  }
}

function connectWebSocket() {
  chrome.storage.local.get(["bridgePort"], (data) => {
    activePort = normalizePort(data.bridgePort);
    const url = `ws://127.0.0.1:${activePort}/ws/tv-sync`;
    const socket = (() => {
      try {
        return new WebSocket(url);
      } catch (e) {
        return null;
      }
    })();

    if (!socket) {
      isConnected = false;
      chrome.storage.local.set({ isConnected: false });
      scheduleReconnect();
      return;
    }

    ws = socket;

    socket.onopen = () => {
      if (ws !== socket) return;
      isConnected = true;
      console.log(`[Kuantra TV Sync] Bridge connected to Kuantra Terminal on port ${activePort}`);
      chrome.storage.local.set({ isConnected: true });
    };

    socket.onmessage = (event) => {
      console.log("[Kuantra TV Sync] Message from terminal:", event.data);
    };

    socket.onclose = () => {
      if (ws !== socket) return;
      isConnected = false;
      chrome.storage.local.set({ isConnected: false });
      scheduleReconnect();
    };

    socket.onerror = () => {
      if (ws !== socket) return;
      isConnected = false;
      chrome.storage.local.set({ isConnected: false });
      closeSocket();
      scheduleReconnect();
    };
  });
}

connectWebSocket();

// Reconnect immediately when the user changes the bridge port in the popup.
chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "local" || !changes.bridgePort) return;
  const nextPort = normalizePort(changes.bridgePort.newValue);
  if (nextPort === activePort && ws && ws.readyState === WebSocket.OPEN) return;
  console.log(`[Kuantra TV Sync] Bridge port changed to ${nextPort}, reconnecting...`);
  isConnected = false;
  chrome.storage.local.set({ isConnected: false });
  closeSocket();
  scheduleReconnect(0);
});

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
      console.log("[Kuantra TV Sync] Forwarded to Kuantra Terminal:", message.symbol);
    }
    sendResponse({ status: "SENT", symbol: message.symbol });
  }
  return true;
});
