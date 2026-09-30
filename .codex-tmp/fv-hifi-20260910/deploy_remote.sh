#!/usr/bin/env bash
set -euo pipefail

root=/opt/cad-analyzer
release=fv-hifi-native-20260910
stamp=$(date -u +%Y%m%dT%H%M%SZ)
snapshot=/opt/cad-analyzer-releases/pre-$release-$stamp
stage=$(mktemp -d /tmp/fv-hifi-code.XXXXXX)
packstage=$(mktemp -d /tmp/fv-hifi-pack.XXXXXX)
packname=TMC-EST-PE-6000-13P-R03_R2018_ASCII_ODA_20260804_162045_fundos_viga_hifi_v20
packroot=$root/scripts/arete/html_fichas/Obra_TREINO_1
target=$packroot/$packname
files='portal/app/fv_ficha.py portal/app/routers/n1_routes.py portal/app/static/fv_ficha.js portal/app/static/fv_ficha.css portal/app/static/drill_grade.js portal/app/templates/obra_detalhe.html'

cleanup() {
  rm -rf "$stage" "$packstage"
  rm -f /tmp/code.tgz /tmp/pack.tgz /tmp/deploy_remote.sh
}
trap cleanup EXIT

mkdir -p "$snapshot"
tar -xzf /tmp/code.tgz -C "$stage"
tar -xzf /tmp/pack.tgz -C "$packstage"
for f in $files; do test -f "$stage/$f"; done
test -f "$packstage/$packname/fundos_viga/V301.html"
count=$(find "$packstage/$packname/fundos_viga" -maxdepth 1 -type f -name 'V*.html' | wc -l)
test "$count" -ge 30
/opt/cad-analyzer/.venv/bin/python -m py_compile \
  "$stage/portal/app/fv_ficha.py" "$stage/portal/app/routers/n1_routes.py"

for f in $files; do
  if test -e "$root/$f"; then
    mkdir -p "$snapshot/$(dirname "$f")"
    cp -a "$root/$f" "$snapshot/$f"
  fi
done
if test -e "$target"; then
  mkdir -p "$snapshot/html_fichas/Obra_TREINO_1"
  cp -a "$target" "$snapshot/html_fichas/Obra_TREINO_1/"
fi

rollback() {
  systemctl stop cad-portal || true
  for f in $files; do
    if test -e "$snapshot/$f"; then
      cp -a "$snapshot/$f" "$root/$f"
    else
      rm -f "$root/$f"
    fi
  done
  rm -rf "$target"
  if test -e "$snapshot/html_fichas/Obra_TREINO_1/$packname"; then
    mkdir -p "$packroot"
    cp -a "$snapshot/html_fichas/Obra_TREINO_1/$packname" "$packroot/"
  fi
  chown -R cadapp:cadapp "$root/portal"
  systemctl start cad-portal || true
}

systemctl stop cad-portal
for f in $files; do
  mkdir -p "$root/$(dirname "$f")"
  cp -a "$stage/$f" "$root/$f"
done
mkdir -p "$packroot"
rm -rf "$target"
cp -a "$packstage/$packname" "$packroot/"
chown -R cadapp:cadapp "$root/portal" "$target"

if ! systemctl start cad-portal; then
  rollback
  exit 1
fi
healthy=0
for attempt in $(seq 1 25); do
  if curl -fsS --max-time 3 http://127.0.0.1:21380/health >/dev/null; then
    healthy=1
    break
  fi
  sleep 1
done
if test "$healthy" != 1; then
  rollback
  exit 1
fi
echo "DEPLOYED snapshot=$snapshot pack_vigas=$count"
