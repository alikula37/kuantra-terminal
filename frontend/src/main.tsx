import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { ThemeProvider } from "./context/ThemeContext";
import { I18nProvider } from "./context/I18nContext";
import { PluginRegistryProvider } from "./context/PluginRegistryContext";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <ThemeProvider>
    <I18nProvider>
      <PluginRegistryProvider>
        <App />
      </PluginRegistryProvider>
    </I18nProvider>
  </ThemeProvider>
);