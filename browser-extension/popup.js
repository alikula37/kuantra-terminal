const DEFAULT_BRIDGE_PORT = 8765;

function normalizePort(value) {
  const port = parseInt(value, 10);
  if (!Number.isFinite(port) || port < 1024 || port > 65535) return null;
  return port;
}

document.addEventListener("DOMContentLoaded", () => {
  const badge = document.getElementById("status-badge");
  const symbolEl = document.getElementById("active-symbol");
  const intervalEl = document.getElementById("active-interval");
  const portInput = document.getElementById("port");
  const saveButton = document.getElementById("save-port");
  const hintEl = document.getElementById("port-hint");

  chrome.storage.local.get(
    ["isConnected", "activeSymbol", "activeInterval", "bridgePort"],
    (data) => {
      if (data.isConnected) {
        badge.textContent = "CONNECTED";
        badge.className = "status-badge online";
      } else {
        badge.textContent = "STANDBY";
        badge.className = "status-badge offline";
      }

      if (data.activeSymbol) symbolEl.textContent = data.activeSymbol;
      if (data.activeInterval) intervalEl.textContent = data.activeInterval;
      portInput.value = normalizePort(data.bridgePort) || DEFAULT_BRIDGE_PORT;
    }
  );

  const savePort = () => {
    const port = normalizePort(portInput.value);
    if (port === null) {
      hintEl.className = "hint";
      hintEl.textContent = "Enter a port between 1024 and 65535.";
      return;
    }
    chrome.storage.local.set({ bridgePort: port }, () => {
      portInput.value = port;
      hintEl.className = "hint saved";
      hintEl.textContent = `Saved. Reconnecting bridge on port ${port}...`;
    });
  };

  saveButton.addEventListener("click", savePort);
  portInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") savePort();
  });
});
