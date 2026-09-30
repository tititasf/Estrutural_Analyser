#!/usr/bin/env bash
set -euo pipefail
root=/opt/cad-analyzer
snapshot=/opt/cad-analyzer-releases/pre-fv-hifi-native-20260910-20260910T032137Z/integrity-hotfix
mkdir -p "$snapshot/portal/app/static"
cp -a "$root/portal/app/fv_ficha.py" "$snapshot/portal/app/fv_ficha.py"
cp -a "$root/portal/app/static/fv_ficha.js" "$snapshot/portal/app/static/fv_ficha.js"
cp -a "$root/portal/app/static/fv_ficha.css" "$snapshot/portal/app/static/fv_ficha.css"
/opt/cad-analyzer/.venv/bin/python -m py_compile /tmp/fv_ficha.py
node --check /tmp/fv_ficha.js
systemctl stop cad-portal
install -o cadapp -g cadapp -m 0644 /tmp/fv_ficha.py "$root/portal/app/fv_ficha.py"
install -o cadapp -g cadapp -m 0644 /tmp/fv_ficha.js "$root/portal/app/static/fv_ficha.js"
install -o cadapp -g cadapp -m 0644 /tmp/fv_ficha.css "$root/portal/app/static/fv_ficha.css"
if ! systemctl start cad-portal; then
  cp -a "$snapshot/portal/app/fv_ficha.py" "$root/portal/app/fv_ficha.py"
  cp -a "$snapshot/portal/app/static/fv_ficha.js" "$root/portal/app/static/fv_ficha.js"
  cp -a "$snapshot/portal/app/static/fv_ficha.css" "$root/portal/app/static/fv_ficha.css"
  chown -R cadapp:cadapp "$root/portal"
  systemctl start cad-portal || true
  exit 1
fi
for attempt in $(seq 1 25); do
  if curl -fsS --max-time 3 http://127.0.0.1:21380/health >/dev/null; then
    rm -f /tmp/fv_ficha.py /tmp/fv_ficha.js /tmp/fv_ficha.css /tmp/deploy_integrity_hotfix.sh
    echo UPDATED
    exit 0
  fi
  sleep 1
done
exit 1
