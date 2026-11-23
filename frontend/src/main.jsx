import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Provider } from "react-redux";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { makeStore } from "./store";
import { ThemeProvider } from "./theme/ThemeContext";
// Fonts are bundled with the app (no request to Google): headings, text, codes.
import "@fontsource-variable/bricolage-grotesque";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <Provider store={makeStore()}>
      <BrowserRouter>
        <AuthProvider>
          <ThemeProvider>
            <App />
          </ThemeProvider>
        </AuthProvider>
      </BrowserRouter>
    </Provider>
  </StrictMode>,
);

// Installable app (US-43). Only in the built app: the dev server reloads too often to cache.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
