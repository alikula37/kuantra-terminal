import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { ThemeProvider } from "./context/ThemeContext";
import { I18nProvider } from "./context/I18nContext";
import { PluginRegistryProvider } from "./context/PluginRegistryContext";
import { resolveBackendUrl } from "./lib/backend";

// The backend port is dynamic in the packaged app; resolve it before any
// component fires its first request.
resolveBackendUrl().finally(() => {
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
