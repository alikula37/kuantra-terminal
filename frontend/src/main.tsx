import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { ThemeProvider } from "./context/ThemeContext";
import { I18nProvider } from "./context/I18nContext";
import { PluginRegistryProvider } from "./context/PluginRegistryContext";
import { bridgeReady } from "./lib/bridge";
import { installPushSink } from "./lib/push";

// Inside the desktop app the Python bridge is injected right after load; wait for it so the
// first requests never fall back to the browser path. In a plain browser this resolves at once.
bridgeReady().finally(() => {
  installPushSink();
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <ThemeProvider>
      <I18nProvider>
        <PluginRegistryProvider>
          <App />
        </PluginRegistryProvider>
      </I18nProvider>
    </ThemeProvider>
  );
});
