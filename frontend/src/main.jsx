import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Provider } from "react-redux";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { makeStore } from "./store";
import "./index.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <Provider store={makeStore()}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </Provider>
  </StrictMode>,
);
