"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { apiGetMe, type UserInfo } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────────

type AuthState =
  | { status: "loading" }
  | { status: "unauthenticated" }
  | { status: "authenticated"; user: UserInfo };

interface AuthContextValue {
  auth: AuthState;
  setUser: (user: UserInfo) => void;
  clearUser: () => void;
}

// ── Context ───────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      const user = await apiGetMe();
      if (cancelled) return;
      setAuth(
        user
          ? { status: "authenticated", user }
          : { status: "unauthenticated" },
      );
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  const setUser = useCallback((user: UserInfo) => {
    setAuth({ status: "authenticated", user });
  }, []);

  const clearUser = useCallback(() => {
    setAuth({ status: "unauthenticated" });
  }, []);

  return (
    <AuthContext.Provider value={{ auth, setUser, clearUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
