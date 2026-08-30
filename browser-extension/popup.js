document.addEventListener("DOMContentLoaded", () => {
  chrome.storage.local.get(["isConnected", "activeSymbol", "activeInterval"], (data) => {
    const badge = document.getElementById("status-badge");
    const symbolEl = document.getElementById("active-symbol");
    const intervalEl = document.getElementById("active-interval");

    if (data.isConnected) {
      badge.textContent = "CONNECTED";
      badge.className = "status-badge online";
    } else {
      badge.textContent = "STANDBY";
      badge.className = "status-badge offline";
    }

    if (data.activeSymbol) symbolEl.textContent = data.activeSymbol;
    if (data.activeInterval) intervalEl.textContent = data.activeInterval;
  });
});