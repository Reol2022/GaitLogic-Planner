#!/usr/bin/env bash
# Read-only metadata audit: no credentials, application data or raw Nginx config.
set -u
set -o pipefail
printf '%s\n' '=== Deployment ==='
printf 'directory: %s\n' "$PWD"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  printf 'git_commit: '; git rev-parse HEAD
  printf 'git_branch: '; git branch --show-current
  printf 'git_changed_entries: '; git status --porcelain | wc -l
else
  printf '%s\n' 'git: not a Git working tree'
fi
python_cmd="${GAITLOGIC_AUDIT_PYTHON:-python3}"
if command -v "$python_cmd" >/dev/null 2>&1; then
  "$python_cmd" --version 2>&1
  "$python_cmd" -m pip show fastapi uvicorn gunicorn mcp 2>/dev/null | awk '/^(Name|Version):/' || true
else
  printf '%s\n' 'python not found; set GAITLOGIC_AUDIT_PYTHON'
fi
printf '%s\n' 'process counts (names only):'
ps -eo comm= | awk '/^(gunicorn|uvicorn|supervisord|nginx)$/ {n[$1]++} END {for (k in n) print k, n[k]}'
if command -v systemctl >/dev/null 2>&1; then
  systemctl list-units --type=service --state=running --no-legend --no-pager 2>/dev/null | awk 'tolower($1) ~ /(gaitlogic|gunicorn|uvicorn|supervisor|nginx)/ {print $1}' || true
fi
printf '%s\n' '=== MCP environment keys (optional; presence only) ==='
env_file="${GAITLOGIC_AUDIT_ENV_FILE:-}"
if [[ -n "$env_file" && -r "$env_file" ]]; then
  for key in MCP_HTTP_ENABLED MCP_OAUTH_ENABLED MCP_PUBLIC_BASE_URL MCP_RESOURCE_URI MCP_ALLOWED_HOSTS MCP_ALLOWED_ORIGINS MCP_OAUTH_ALLOWED_REDIRECT_HOSTS JWT_SECRET_KEY; do
    if grep -qE "^[[:space:]]*(export[[:space:]]+)?${key}[[:space:]]*=" "$env_file"; then
      printf '%s: present (value not checked)\n' "$key"
    else
      printf '%s: absent\n' "$key"
    fi
  done
else
  printf '%s\n' 'skipped; optionally set GAITLOGIC_AUDIT_ENV_FILE to the active environment file'
fi
printf '%s\n' '=== TLS (optional) ==='
domain="${GAITLOGIC_AUDIT_DOMAIN:-}"
if [[ -n "$domain" && "$domain" =~ ^[A-Za-z0-9.-]+$ ]] && command -v openssl >/dev/null 2>&1; then
  printf 'domain: %s\n' "$domain"
  if command -v getent >/dev/null 2>&1; then getent ahosts "$domain" | awk '{print $1}' | sort -u || true; fi
  if timeout 12 openssl s_client -connect "$domain:443" -servername "$domain" -verify_hostname "$domain" -verify_return_error </dev/null 2>/dev/null | openssl x509 -noout -dates -ext subjectAltName 2>/dev/null; then
    printf '%s\n' 'certificate metadata displayed; independently verify chain as described in the runbook'
  else
    printf '%s\n' 'certificate metadata unavailable or verification failed'
  fi
  for path in /api/health /mcp /.well-known/oauth-protected-resource/mcp /.well-known/oauth-authorization-server/oauth; do
    if command -v curl >/dev/null 2>&1; then
      status=$(curl --silent --show-error --max-time 8 --output /dev/null --write-out '%{http_code}' "https://$domain$path" 2>/dev/null) || status='TLS_OR_NETWORK_ERROR'
      printf '%s %s\n' "$path" "$status"
    fi
  done
else
  printf '%s\n' 'skipped; set GAITLOGIC_AUDIT_DOMAIN to the confirmed hostname'
fi
printf '%s\n' '=== MySQL metadata (optional) ==='
db="${GAITLOGIC_AUDIT_DB:-}"
login="${GAITLOGIC_AUDIT_MYSQL_LOGIN_PATH:-}"
if [[ "$db" =~ ^[A-Za-z0-9_]+$ && "$login" =~ ^[A-Za-z0-9_-]+$ ]] && command -v mysql >/dev/null 2>&1; then
  mysql --login-path="$login" --batch --skip-column-names --connect-timeout=5 -e "SELECT VERSION(); SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA='$db' AND TABLE_NAME IN ('mcp_oauth_clients','mcp_oauth_authorization_codes','mcp_oauth_refresh_tokens','mcp_oauth_grants') ORDER BY TABLE_NAME; SELECT TABLE_NAME,COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='$db' AND TABLE_NAME IN ('mcp_oauth_authorization_codes','mcp_oauth_refresh_tokens','mcp_oauth_grants') AND COLUMN_NAME IN ('resource_uri','grant_id','revoked_at') ORDER BY TABLE_NAME,COLUMN_NAME; SELECT TABLE_NAME,INDEX_NAME,NON_UNIQUE,COLUMN_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA='$db' AND TABLE_NAME IN ('mcp_oauth_authorization_codes','mcp_oauth_refresh_tokens','mcp_oauth_grants') ORDER BY TABLE_NAME,INDEX_NAME,SEQ_IN_INDEX;" 2>/dev/null || printf '%s\n' 'MySQL metadata unavailable; check read-only login path and privileges'
else
  printf '%s\n' 'skipped; set GAITLOGIC_AUDIT_DB and GAITLOGIC_AUDIT_MYSQL_LOGIN_PATH'
fi
printf '%s\n' 'Nginx: inspect the active BaoTa site; redact nginx -T before sharing.'
