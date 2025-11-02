import React from "react";
import ReactDOM from "react-dom/client";
import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";
import { QueryClient, QueryClientProvider } from "react-query";
import { I18nextProvider } from "react-i18next";

import App from "./App";
import "./styles.css";
import i18n from "./services/i18n";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#1a73e8"
    },
    secondary: {
      main: "#fbbc04"
    }
  },
  typography: {
    fontFamily: ["Inter", "Roboto", "sans-serif"].join(",")
  }
});

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <App />
        </ThemeProvider>
      </QueryClientProvider>
    </I18nextProvider>
  </React.StrictMode>
);
