#!/usr/bin/env bash
# Publica uma versão da tiltados_api no servidor. Executado pelo GitHub Actions,
# via SSH, como o usuário "deploy":
#
#   ssh deploy@servidor 'bash -s -- /tmp/release.tgz 20261018-1530-abc1234' < deploy/publicar.sh
#
# Extrai o pacote em releases/<nome>, prepara o ambiente Python (reaproveitado
# enquanto o requirements.txt não muda), aponta "current" para a versão nova,
# reinicia o serviço e confere se a API responde. Se não responder, volta para a
# versão anterior.
set -euo pipefail

TARBALL="$1"
NAME="$2"
BASE=/opt/tiltados_api
SERVICE=tiltados-api
OLD_SERVICE=tiltados-api-legacy
KEEP=3
HEALTH_URLS=(
  http://127.0.0.1:8000/
  http://127.0.0.1:8000/load/2026/standings/drivers
)
SYSTEMCTL="$(command -v systemctl)"

REL="$BASE/releases/$NAME"
# Versão no ar antes desta publicação (vazio na primeira). Só lê o link se ele
# existir: "readlink -f" de um caminho inexistente devolve o próprio caminho.
PREV=""
if [[ -L "$BASE/current" ]]; then
  PREV="$(readlink -f "$BASE/current")"
fi
MIGRATED=0

point_current_to() {
  ln -sfn "$1" "$BASE/current.tmp"
  mv -Tf "$BASE/current.tmp" "$BASE/current"
}

healthy() {
  local url
  for url in "${HEALTH_URLS[@]}"; do
    for attempt in $(seq 1 30); do
      if curl -fs -o /dev/null --max-time 10 "$url"; then
        break
      fi
      if [[ $attempt -eq 30 ]]; then
        # Mostra a resposta da API (em erro de dados, a causa vem em "detail").
        echo "!! $url não respondeu:" >&2
        curl -sS --max-time 10 "$url" 2>&1 | head -c 500 >&2 || true
        echo >&2
        return 1
      fi
      sleep 1
    done
  done
}

echo "==> Extraindo $NAME"
rm -rf "$REL"
mkdir -p "$REL"
tar -xzf "$TARBALL" -C "$REL"
rm -f "$TARBALL"

# Até a ativação, qualquer falha descarta a versão nova e deixa a atual no ar.
trap 'rm -rf "$REL"' ERR

# Um ambiente por versão do requirements.txt: publicações que só trazem CSVs
# novos reaproveitam o ambiente e não instalam nada.
echo "==> Preparando o ambiente Python"
REQ_HASH="$(sha256sum "$REL/requirements.txt" | cut -c1-16)"
VENV="$BASE/venvs/$REQ_HASH"
if [[ -f "$VENV/.pronto" ]]; then
  echo "    reaproveitando o ambiente $REQ_HASH"
else
  echo "    requirements.txt mudou: criando o ambiente $REQ_HASH"
  rm -rf "$VENV"
  python3 -m venv "$VENV"
  "$VENV/bin/python" -m pip install --quiet --disable-pip-version-check -r "$REL/requirements.txt"
  touch "$VENV/.pronto"
fi
ln -sfn "$VENV" "$REL/.venv"

trap - ERR

echo "==> Ativando $NAME"
point_current_to "$REL"

# Primeira publicação: desliga a instalação antiga, que ocupa a porta 8000.
if "$SYSTEMCTL" is-active --quiet "$OLD_SERVICE"; then
  echo "==> Desligando a instalação antiga ($OLD_SERVICE)"
  sudo "$SYSTEMCTL" disable --now "$OLD_SERVICE"
  MIGRATED=1
fi

sudo "$SYSTEMCTL" restart "$SERVICE"

echo "==> Conferindo ${HEALTH_URLS[*]}"
if healthy; then
  echo "==> No ar: $NAME"
else
  echo "!! A API não respondeu; desfazendo a publicação" >&2
  if [[ -n "$PREV" && -d "$PREV" ]]; then
    point_current_to "$PREV"
    sudo "$SYSTEMCTL" restart "$SERVICE"
  elif [[ $MIGRATED -eq 1 ]]; then
    sudo "$SYSTEMCTL" stop "$SERVICE"
    sudo "$SYSTEMCTL" enable --now "$OLD_SERVICE"
  fi
  rm -rf "$REL"
  exit 1
fi

# Mantém só as últimas versões (a no ar inclusive) para permitir voltar atrás,
# e apaga os ambientes Python que nenhuma delas usa mais.
ls -1dt "$BASE"/releases/*/ | tail -n +$((KEEP + 1)) | xargs -r rm -rf
for venv in "$BASE"/venvs/*/; do
  venv="${venv%/}"
  [[ -d "$venv" ]] || continue
  in_use=0
  for rel in "$BASE"/releases/*/; do
    if [[ "$(readlink -f "${rel%/}/.venv")" == "$venv" ]]; then
      in_use=1
    fi
  done
  if [[ $in_use -eq 0 ]]; then
    rm -rf "$venv"
  fi
done
