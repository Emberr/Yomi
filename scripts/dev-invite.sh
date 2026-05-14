#!/usr/bin/env bash
# Create a single-use invite code by logging in as admin via the API.
#
# Usage:
#   ADMIN_USER=admin ADMIN_PASS=changeme ./scripts/dev-invite.sh
#
# Optional env vars:
#   BASE_URL      default: http://localhost:8888
#   ADMIN_USER    admin username (or prompts)
#   ADMIN_PASS    admin password (or prompts)
#   ADMIN_INVITE  if set to "1", creates an admin-level invite (default: 0)

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8888}"
COOKIES="$(mktemp)"
trap 'rm -f "$COOKIES"' EXIT

if [[ -z "${ADMIN_USER:-}" ]]; then
  read -rp "Admin username: " ADMIN_USER
fi
if [[ -z "${ADMIN_PASS:-}" ]]; then
  read -rsp "Admin password: " ADMIN_PASS
  echo
fi
IS_ADMIN_INVITE="${ADMIN_INVITE:-0}"

# 1. Fetch CSRF token
CSRF_RESPONSE=$(curl -sf -c "$COOKIES" "${BASE_URL}/api/auth/csrf-token")
CSRF_TOKEN=$(printf '%s' "$CSRF_RESPONSE" | grep -o '"csrf_token":"[^"]*"' | cut -d'"' -f4)
if [[ -z "$CSRF_TOKEN" ]]; then
  printf 'ERROR: Could not fetch CSRF token. Is the stack running?\n' >&2
  exit 1
fi

# 2. Log in
LOGIN_RESPONSE=$(curl -sf -b "$COOKIES" -c "$COOKIES" \
  -X POST "${BASE_URL}/api/auth/login" \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -d "{\"username\":\"${ADMIN_USER}\",\"password\":\"${ADMIN_PASS}\"}")
if ! printf '%s' "$LOGIN_RESPONSE" | grep -q '"error":null'; then
  printf 'ERROR: Login failed: %s\n' "$LOGIN_RESPONSE" >&2
  exit 1
fi

# 3. Refresh CSRF after login (session cookie changed)
CSRF_RESPONSE=$(curl -sf -b "$COOKIES" -c "$COOKIES" "${BASE_URL}/api/auth/csrf-token")
CSRF_TOKEN=$(printf '%s' "$CSRF_RESPONSE" | grep -o '"csrf_token":"[^"]*"' | cut -d'"' -f4)

# 4. Create invite
IS_ADMIN_BOOL="false"
[[ "$IS_ADMIN_INVITE" == "1" ]] && IS_ADMIN_BOOL="true"

INVITE_RESPONSE=$(curl -sf -b "$COOKIES" -c "$COOKIES" \
  -X POST "${BASE_URL}/api/admin/invites" \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -d "{\"is_admin\":${IS_ADMIN_BOOL}}")

if ! printf '%s' "$INVITE_RESPONSE" | grep -q '"error":null'; then
  printf 'ERROR: Invite creation failed: %s\n' "$INVITE_RESPONSE" >&2
  exit 1
fi

INVITE_CODE=$(printf '%s' "$INVITE_RESPONSE" | grep -o '"code":"[^"]*"' | cut -d'"' -f4)
printf '\nInvite code: %s\n' "$INVITE_CODE"
printf 'Register at: %s/register\n' "$BASE_URL"
