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
      main: "#3358ff",
      light: "#5f7cff",
      dark: "#1235b9"
    },
    secondary: {
      main: "#ffb547"
    },
    background: {
      default: "#f3f5ff",
      paper: "#ffffff"
    },
    success: {
      main: "#21c58b"
    },
    warning: {
      main: "#ffa726"
    }
  },
  typography: {
    fontFamily: ['"Inter"', '"Segoe UI"', "Roboto", "sans-serif"].join(","),
    h4: {
      fontWeight: 600,
      letterSpacing: "-0.01em"
    },
    h6: {
      fontWeight: 600
    },
    button: {
      fontWeight: 600,
      textTransform: "none"
    }
  },
  shape: {
    borderRadius: 16
  },
  components: {
    MuiAppBar: {
      styleOverrides: {
        root: {
          background: "linear-gradient(135deg, #2b4bff 0%, #597bff 100%)",
          boxShadow: "0 10px 30px -12px rgba(43, 75, 255, 0.55)"
        }
      }
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 20,
          border: "1px solid rgba(51, 88, 255, 0.08)",
          boxShadow: "0 24px 50px -28px rgba(51, 88, 255, 0.45)"
        }
      }
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 999,
          paddingInline: "1.5rem",
          paddingBlock: "0.55rem"
        }
      }
    },
    MuiTabs: {
      styleOverrides: {
        indicator: {
          height: 4,
          borderRadius: 4
        }
      }
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: "none",
          fontWeight: 600,
          fontSize: "1rem",
          minHeight: 48
        }
      }
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
          borderRadius: 999
        }
      }
    },
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          minHeight: "100%",
          backgroundRepeat: "no-repeat"
        }
      }
    }
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
