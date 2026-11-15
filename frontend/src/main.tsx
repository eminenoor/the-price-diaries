// Fonts, self-hosted. Latin plus Latin Extended for Turkish letters (ş, ğ, ı).
import "@fontsource/bricolage-grotesque/latin-800.css";
import "@fontsource/bricolage-grotesque/latin-ext-800.css";
import "@fontsource/figtree/latin-500.css";
import "@fontsource/figtree/latin-ext-500.css";
import "@fontsource/figtree/latin-500-italic.css";
import "@fontsource/figtree/latin-700.css";
import "@fontsource/figtree/latin-ext-700.css";
import "@fontsource/nanum-pen-script/latin-400.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/night.css";
import "./styles/quiet.css";
import "./styles/room.css";
import "./styles/note.css";
import "./styles/notes.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { ModeProvider } from "./mode";

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ModeProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </ModeProvider>
    </QueryClientProvider>
  </StrictMode>,
);
