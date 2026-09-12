#!/usr/bin/env bash
# Publicação reversível do CAD-Analyzer na VPS Hetzner.
# Uso: ./portal/ops/deploy_vps.sh --release-id <rótulo> [--apply]
# --apply exige CONFIRM_VPS_DEPLOY=YES e altera a VPS.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HOST="${VPS_HOST:-root@62.238.111.147}"
REMOTE_ROOT="${VPS_ROOT:-/opt/cad-analyzer}"
RELEASE_ID=""
APPLY=0

while (($#)); do
  case "$1" in
    --release-id) RELEASE_ID="${2:?missing release id}"; shift 2 ;;
    --apply) APPLY=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ "$RELEASE_ID" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "release id inválido" >&2; exit 2; }
for path in src portal scripts docs CLAUDE.md requirements.txt consulta-publica-api; do
  [[ -e "$ROOT/$path" ]] || { echo "ausente no pacote: $path" >&2; exit 2; }
done

if (( ! APPLY )); then
  echo "Preflight OK. Nenhuma escrita: use CONFIRM_VPS_DEPLOY=YES $0 --release-id $RELEASE_ID --apply"
  exit 0
fi
[[ "${CONFIRM_VPS_DEPLOY:-}" == "YES" ]] || { echo "Defina CONFIRM_VPS_DEPLOY=YES para publicar." >&2; exit 2; }

bundle="$(mktemp "${TMPDIR:-/tmp}/cad-analyzer-${RELEASE_ID}.XXXXXX.tgz")"
trap 'rm -f "$bundle"' EXIT
tar -C "$ROOT" -czf "$bundle" \
  --exclude='scripts/arete/html_fichas' --exclude='scripts/arete/relatorios' \
  --exclude='scripts/arete/tmp' --exclude='DADOS-OBRAS' --exclude='GOLDEN' \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache' \
  src portal scripts docs CLAUDE.md requirements.txt consulta-publica-api

remote_stage="/tmp/cad-analyzer-${RELEASE_ID}.tgz"
scp "$bundle" "$HOST:$remote_stage"
ssh "$HOST" "REMOTE_ROOT='$REMOTE_ROOT' RELEASE_ID='$RELEASE_ID' BUNDLE='$remote_stage' bash -s" <<'REMOTE'
set -euo pipefail
releases="${REMOTE_ROOT}-releases"
snapshot="$releases/pre-${RELEASE_ID}-$(date -u +%Y%m%dT%H%M%SZ)"
stage="$(mktemp -d /tmp/cad-analyzer-stage.XXXXXX)"
cleanup() { rm -rf "$stage" "$BUNDLE"; }
trap cleanup EXIT
mkdir -p "$releases"
tar -xzf "$BUNDLE" -C "$stage"
test -f "$stage/portal/run_dev.py"
test -f "$stage/src/core/pillar_face_beams.py"
mkdir "$snapshot"
for path in src portal scripts docs CLAUDE.md requirements.txt consulta-publica-api; do
  [[ -e "$REMOTE_ROOT/$path" ]] && cp -a "$REMOTE_ROOT/$path" "$snapshot/"
done
printf '%s\n' "$RELEASE_ID" > "$snapshot/release-id.txt"

rollback() {
  systemctl stop cad-portal || true
  for path in src portal scripts docs CLAUDE.md requirements.txt consulta-publica-api; do
    rm -rf "$REMOTE_ROOT/$path"
    [[ -e "$snapshot/$path" ]] && cp -a "$snapshot/$path" "$REMOTE_ROOT/"
  done
  systemctl start cad-portal || true
}
systemctl stop cad-portal
# Copiar apenas os componentes versionados. Nunca copie "$stage/." inteiro:
# o diretório criado por mktemp é 0700/root e transferiria essa permissão ao
# próprio REMOTE_ROOT, bloqueando o usuário cadapp do systemd.
if ! for path in src portal scripts docs CLAUDE.md requirements.txt consulta-publica-api; do
  rm -rf "$REMOTE_ROOT/$path"
  cp -a "$stage/$path" "$REMOTE_ROOT/"
done; then rollback; exit 1; fi
chown -R cadapp:cadapp "$REMOTE_ROOT/src" "$REMOTE_ROOT/portal" "$REMOTE_ROOT/scripts" "$REMOTE_ROOT/docs" "$REMOTE_ROOT/consulta-publica-api"
chown cadapp:cadapp "$REMOTE_ROOT/CLAUDE.md" "$REMOTE_ROOT/requirements.txt"
if ! systemctl start cad-portal; then
  rollback
  exit 1
fi
for attempt in {1..20}; do
  if curl --fail --silent --show-error --max-time 3 http://127.0.0.1:21380/health >/dev/null; then
    break
  fi
  sleep 1
done
if ! curl --fail --silent --show-error --max-time 3 http://127.0.0.1:21380/health >/dev/null; then
  rollback
  exit 1
fi
printf 'DEPLOYED %s snapshot=%s\n' "$RELEASE_ID" "$snapshot"
REMOTE
for attempt in {1..20}; do
  if curl --fail --silent --show-error --max-time 3 https://cad-analyzer.duckdns.org/health >/dev/null; then
    echo "Deploy $RELEASE_ID concluído e health checks aprovados."
    exit 0
  fi
  sleep 1
done
echo "Health check HTTPS externo falhou após publicação; o serviço local permanece saudável." >&2
exit 1
