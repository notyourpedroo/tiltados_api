#!/usr/bin/env bash
# Prepara o servidor para o deploy automático da tiltados_api (rodar UMA vez, como root).
#
#   bash setup-servidor.sh ["ssh-ed25519 AAAA... github-actions-tiltados"]
#
# A chave pública é opcional se o usuário "deploy" já existir com a chave do
# deploy cadastrada.
#
# O que faz:
# - garante o usuário "deploy" e a chave pública informada;
# - move a instalação atual (/opt/tiltados_api) para /opt/tiltados_api_legacy e a
#   mantém no ar como tiltados-api-legacy.service, com a mesma configuração de hoje;
# - cria a nova /opt/tiltados_api (releases/, venvs/ e o link "current");
# - reescreve tiltados-api.service para rodar a versão publicada, como "deploy", sem root;
# - permite ao "deploy" apenas reiniciar/parar esse serviço e desligar/religar o legado.
#
# A API fica fora do ar só por alguns segundos, durante a troca para o serviço legado.
# Se o legado não responder, o script desfaz a troca. A primeira publicação pelo
# GitHub Actions desliga o legado e liga o serviço novo.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Rode como root." >&2
  exit 1
fi
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != ssh-* ) ]]; then
  echo "Uso: bash $0 [\"<chave publica ssh do deploy>\"]" >&2
  exit 1
fi
PUBKEY="${1:-}"

APP_USER=deploy
BASE=/opt/tiltados_api
LEGACY_DIR=/opt/tiltados_api_legacy
SERVICE=tiltados-api
LEGACY_SERVICE=tiltados-api-legacy
UNIT_DIR=/etc/systemd/system
HEALTH_URL=http://127.0.0.1:8000/
SYSTEMCTL="$(command -v systemctl)"

wait_for_api() {
  for _ in $(seq 1 30); do
    if curl -fs -o /dev/null --max-time 5 "$HEALTH_URL"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

# 0. Pré-requisitos: curl e o módulo venv do Python (pacote python3-venv no Ubuntu).
command -v curl >/dev/null || { echo "Instale o curl: apt install curl" >&2; exit 1; }
TMP_VENV="$(mktemp -d)"
if ! python3 -m venv "$TMP_VENV/v" >/dev/null 2>&1; then
  rm -rf "$TMP_VENV"
  echo "Instale o suporte a venv do Python: apt install python3-venv" >&2
  exit 1
fi
rm -rf "$TMP_VENV"

# 1. Usuário de deploy (sem senha; entra só por chave).
if ! id "$APP_USER" &>/dev/null; then
  if [[ -z "$PUBKEY" ]]; then
    echo "O usuário '$APP_USER' não existe: informe a chave pública do deploy." >&2
    exit 1
  fi
  useradd --system --create-home --shell /bin/bash "$APP_USER"
fi
HOME_DIR="$(getent passwd "$APP_USER" | cut -d: -f6)"
install -d -m 700 -o "$APP_USER" -g "$APP_USER" "$HOME_DIR/.ssh"
AUTH="$HOME_DIR/.ssh/authorized_keys"
touch "$AUTH"
# "restrict" bloqueia encaminhamento de portas, agente e terminal interativo;
# comandos e cópia de arquivos (scp) continuam funcionando.
if [[ -n "$PUBKEY" ]] && ! grep -qF "$PUBKEY" "$AUTH"; then
  echo "restrict $PUBKEY" >>"$AUTH"
fi
chown "$APP_USER:$APP_USER" "$AUTH"
chmod 600 "$AUTH"
if [[ ! -s "$AUTH" ]]; then
  echo "Nenhuma chave cadastrada para '$APP_USER': informe a chave pública do deploy." >&2
  exit 1
fi

# 2. Arquivo do serviço novo: roda a versão publicada em $BASE/current.
NEW_UNIT="$(cat <<EOF
[Unit]
Description=Tiltados API (FastAPI)
After=network.target
# Só sobe depois que a primeira versão tiver sido publicada.
ConditionPathExists=$BASE/current/main.py

[Service]
User=$APP_USER
WorkingDirectory=$BASE/current
ExecStart=$BASE/current/.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
)"

# 3. Migração da instalação atual (só na primeira vez).
if [[ -e "$BASE/current" || -d "$BASE/releases" ]]; then
  echo "==> Migração já feita antes; atualizando só o serviço e as permissões"
elif [[ -d "$BASE" ]]; then
  if [[ -e "$LEGACY_DIR" ]]; then
    echo "$LEGACY_DIR já existe; confira antes de rodar de novo." >&2
    exit 1
  fi

  echo "==> Guardando a configuração atual do $SERVICE"
  BACKUP_UNIT="/root/$SERVICE.service.antes-do-deploy"
  cp "$UNIT_DIR/$SERVICE.service" "$BACKUP_UNIT"

  # O .venv antigo é chamado via "python -m uvicorn", que continua funcionando
  # depois que a pasta muda de lugar.
  cat >"$UNIT_DIR/$LEGACY_SERVICE.service" <<EOF
[Unit]
Description=Tiltados API (instalação antiga, até a primeira publicação automática)
After=network.target

[Service]
User=root
WorkingDirectory=$LEGACY_DIR
ExecStart=$LEGACY_DIR/.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
EOF

  echo "==> Trocando para o serviço legado (alguns segundos fora do ar)"
  "$SYSTEMCTL" stop "$SERVICE"
  mv "$BASE" "$LEGACY_DIR"
  printf '%s\n' "$NEW_UNIT" >"$UNIT_DIR/$SERVICE.service"
  "$SYSTEMCTL" daemon-reload
  "$SYSTEMCTL" enable --now "$LEGACY_SERVICE"

  if ! wait_for_api; then
    echo "!! O serviço legado não respondeu; desfazendo a troca" >&2
    "$SYSTEMCTL" disable --now "$LEGACY_SERVICE" || true
    rm -f "$UNIT_DIR/$LEGACY_SERVICE.service"
    mv "$LEGACY_DIR" "$BASE"
    cp "$BACKUP_UNIT" "$UNIT_DIR/$SERVICE.service"
    "$SYSTEMCTL" daemon-reload
    "$SYSTEMCTL" start "$SERVICE"
    exit 1
  fi
  echo "==> API no ar pelo serviço legado ($LEGACY_DIR)"
fi

# 4. Pastas das versões publicadas e dos ambientes Python.
install -d -o "$APP_USER" -g "$APP_USER" "$BASE" "$BASE/releases" "$BASE/venvs"
printf '%s\n' "$NEW_UNIT" >"$UNIT_DIR/$SERVICE.service"

# 5. Permissões mínimas do "deploy" (apenas estes comandos, sem senha).
SUDOERS=/etc/sudoers.d/$SERVICE
cat >"$SUDOERS.tmp" <<EOF
$APP_USER ALL=(root) NOPASSWD: $SYSTEMCTL restart $SERVICE, $SYSTEMCTL stop $SERVICE, $SYSTEMCTL disable --now $LEGACY_SERVICE, $SYSTEMCTL enable --now $LEGACY_SERVICE
EOF
chmod 440 "$SUDOERS.tmp"
visudo -cf "$SUDOERS.tmp" >/dev/null
mv "$SUDOERS.tmp" "$SUDOERS"

"$SYSTEMCTL" daemon-reload
"$SYSTEMCTL" enable "$SERVICE" >/dev/null

echo "Pronto. Pasta $BASE, serviço $SERVICE e permissões do '$APP_USER' preparados."
echo "A API segue no ar; a primeira publicação pelo GitHub Actions faz a troca."
