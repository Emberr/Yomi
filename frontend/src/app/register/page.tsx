"use client";

import { type FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { apiRegister } from "@/lib/api";

function RegisterForm() {
  const { auth, setUser } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [inviteCode, setInviteCode] = useState(
    searchParams.get("invite") ?? "",
  );
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
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
      const result = await apiRegister({
        invite_code: inviteCode,
        username,
        display_name: displayName,
        password,
      });
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
        <h1 className="auth-heading">Create account</h1>

        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}

        <form onSubmit={(e) => { void handleSubmit(e); }}>
          <div className="form-field">
            <label className="form-label" htmlFor="invite-code">
              Invite code
            </label>
            <input
              className="form-input"
              disabled={pending}
              id="invite-code"
              onChange={(e) => setInviteCode(e.target.value)}
              placeholder="Paste your invite code"
              required
              type="text"
              value={inviteCode}
            />
          </div>

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
              pattern="[A-Za-z0-9_]{3,32}"
              required
              title="3–32 characters: letters, digits, or underscores"
              type="text"
              value={username}
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="display-name">
              Display name
            </label>
            <input
              autoComplete="name"
              className="form-input"
              disabled={pending}
              id="display-name"
              onChange={(e) => setDisplayName(e.target.value)}
              required
              type="text"
              value={displayName}
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="password">
              Password
            </label>
            <input
              autoComplete="new-password"
              className="form-input"
              disabled={pending}
              id="password"
              minLength={8}
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
            {pending ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="form-footer">
          Already have an account?{" "}
          <a href="/login">Sign in</a>
        </p>
      </div>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense
      fallback={
        <div className="auth-page">
          <div className="auth-panel">
            <p>Loading…</p>
          </div>
        </div>
      }
    >
      <RegisterForm />
    </Suspense>
  );
}
