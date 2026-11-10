import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

/** Night view (default) or quiet mode, a daylight poster. */
export type Mode = "night" | "quiet";

const KEY = "price-diaries:mode";

/** localStorage can be missing or throw (private windows, blocked storage). */
function readMode(): Mode {
  try {
    return window.localStorage.getItem(KEY) === "quiet" ? "quiet" : "night";
  } catch {
    return "night";
  }
}

function saveMode(mode: Mode): void {
  try {
    window.localStorage.setItem(KEY, mode);
  } catch {
    // Not saved; the toggle still works for this visit.
  }
}

const ModeContext = createContext<{ mode: Mode; setMode: (mode: Mode) => void }>({
  mode: "night",
  setMode: () => undefined,
});

export function ModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>(readMode);
  useEffect(() => {
    document.documentElement.dataset.mode = mode;
    saveMode(mode);
  }, [mode]);
  return <ModeContext.Provider value={{ mode, setMode }}>{children}</ModeContext.Provider>;
}

export const useMode = () => useContext(ModeContext);
