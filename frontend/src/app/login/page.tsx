"use client";

import { type FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { apiLogin } from "@/lib/api";

export default function LoginPage() {
  const { auth, setUser } = useAuth();
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (auth.status === "authenticated") {
      router.replace("/");
    }
  }, [auth.status, router]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setPending(true);
    try {
      const result = await apiLogin(username, password);
      if (!result.ok) {
        setError(result.error);
      } else {
        setUser(result.data);
        router.push("/");
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setPending(false);
    }
  }

  if (auth.status === "authenticated") return null;

  return (
    <div className="auth-page">
      <div className="auth-panel">
        <h1 className="auth-heading">Sign in</h1>

        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}

        <form onSubmit={(e) => { void handleSubmit(e); }}>
          <div className="form-field">
            <label className="form-label" htmlFor="username">
              Username
            </label>
            <input
              autoComplete="username"
              className="form-input"
              disabled={pending}
              id="username"
              onChange={(e) => setUsername(e.target.value)}
              required
              type="text"
              value={username}
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="password">
              Password
            </label>
            <input
              autoComplete="current-password"
              className="form-input"
              disabled={pending}
              id="password"
              onChange={(e) => setPassword(e.target.value)}
              required
              type="password"
              value={password}
            />
          </div>

          <button
            className="btn btn-primary"
            disabled={pending}
            type="submit"
          >
            {pending ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="form-footer">
          Have an invite code?{" "}
          <a href="/register">Create account</a>
        </p>
      </div>
    </div>
  );
}
