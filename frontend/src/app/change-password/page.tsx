"use client";

import { type FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { apiChangePassword } from "@/lib/api";

export default function ChangePasswordPage() {
  const { auth } = useAuth();
  const router = useRouter();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (auth.status === "unauthenticated") {
      router.replace("/login");
    }
  }, [auth.status, router]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }
    setError("");
    setPending(true);
    try {
      const result = await apiChangePassword(currentPassword, newPassword);
      if (!result.ok) {
        setError(result.error);
      } else {
        setSuccess(true);
        setTimeout(() => router.push("/"), 2000);
      }
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setPending(false);
    }
  }

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return null;
  }

  const isDisabled = pending || success;

  return (
    <div className="auth-page">
      <div className="auth-panel">
        <h1 className="auth-heading">Change password</h1>

        {error && (
          <div className="form-error" role="alert">
            {error}
          </div>
        )}
        {success && (
          <div className="form-success" role="status">
            Password changed successfully. Redirecting…
          </div>
        )}

        <form onSubmit={(e) => { void handleSubmit(e); }}>
          <div className="form-field">
            <label className="form-label" htmlFor="current-password">
              Current password
            </label>
            <input
              autoComplete="current-password"
              className="form-input"
              disabled={isDisabled}
              id="current-password"
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              type="password"
              value={currentPassword}
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="new-password">
              New password
            </label>
            <input
              autoComplete="new-password"
              className="form-input"
              disabled={isDisabled}
              id="new-password"
              minLength={8}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              type="password"
              value={newPassword}
            />
          </div>

          <div className="form-field">
            <label className="form-label" htmlFor="confirm-password">
              Confirm new password
            </label>
            <input
              autoComplete="new-password"
              className="form-input"
              disabled={isDisabled}
              id="confirm-password"
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              type="password"
              value={confirmPassword}
            />
          </div>

          <button
            className="btn btn-primary"
            disabled={isDisabled}
            type="submit"
          >
            {pending ? "Changing password…" : "Change password"}
          </button>
        </form>

        <p className="form-footer">
          <a href="/">Back to dashboard</a>
        </p>
      </div>
    </div>
  );
}
