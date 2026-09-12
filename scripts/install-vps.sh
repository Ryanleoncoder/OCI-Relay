#!/usr/bin/env bash
#
# Instala o OCI Relay como serviço systemd numa VPS Linux.
#
# Rode NA VPS, como um usuário com sudo:
#   curl -fsSL <raw-url>/scripts/install-vps.sh | bash
# ou, com o repositório já clonado:
#   ./scripts/install-vps.sh
#
# Não recebe segredos por argumento: eles vão para /etc/oci-relay/.env,
# que o script cria a partir do .env.example para você editar.

set -euo pipefail

REPO="${OCI_RELAY_REPO:-https://github.com/Ryanleoncoder/OCI-Relay.git}"
DESTINO="${OCI_RELAY_HOME:-/opt/oci-relay}"
DIR_CONFIG="/etc/oci-relay"
DIR_ESTADO="/var/lib/oci-relay"
SERVICO="oci-relay"
USUARIO="${SUDO_USER:-$USER}"

info()  { printf '\033[36m==>\033[0m %s\n' "$1"; }
ok()    { printf '\033[32m  ok\033[0m %s\n' "$1"; }
aviso() { printf '\033[33m  !!\033[0m %s\n' "$1"; }
erro()  { printf '\033[31merro:\033[0m %s\n' "$1" >&2; exit 1; }

[[ $EUID -eq 0 ]] && erro "não rode como root; use um usuário com sudo."
command -v sudo  >/dev/null || erro "sudo não encontrado."
command -v git   >/dev/null || erro "git não encontrado. Instale com: sudo apt install git"
command -v python3 >/dev/null || erro "python3 não encontrado."

# O projeto exige 3.10+ (union types com |, match de tipos modernos).
python3 - <<'PY' || erro "Python 3.10+ é necessário."
import sys
sys.exit(0 if sys.version_info >= (3, 10) else 1)
PY
ok "python $(python3 -V | cut -d' ' -f2)"

# ── Código ───────────────────────────────────────────────────────────────
info "Instalando o código em $DESTINO"
if [[ -d "$DESTINO/.git" ]]; then
    sudo git -C "$DESTINO" pull --ff-only
    ok "repositório atualizado"
else
    sudo mkdir -p "$DESTINO"
    sudo chown "$USUARIO:$USUARIO" "$DESTINO"
    git clone "$REPO" "$DESTINO"
    ok "repositório clonado"
fi
sudo chown -R "$USUARIO:$USUARIO" "$DESTINO"

# ── Dependências ─────────────────────────────────────────────────────────
info "Criando ambiente virtual"
if ! python3 -m venv "$DESTINO/.venv" 2>/dev/null; then
    erro "falha ao criar venv. Instale com: sudo apt install python3-venv"
fi
"$DESTINO/.venv/bin/pip" install --quiet --upgrade pip
"$DESTINO/.venv/bin/pip" install --quiet -r "$DESTINO/requirements.txt"
ok "dependências instaladas"

# ── Configuração ─────────────────────────────────────────────────────────
info "Preparando $DIR_CONFIG"
sudo mkdir -p "$DIR_CONFIG"
if [[ -f "$DIR_CONFIG/.env" ]]; then
    ok ".env já existe, preservado"
    CONFIG_NOVA=0
else
    sudo cp "$DESTINO/.env.example" "$DIR_CONFIG/.env"
    # Na VPS o modo correto é Instance Principal: nenhuma chave em disco.
    sudo sed -i 's|^OCI_USE_INSTANCE_PRINCIPAL=.*|OCI_USE_INSTANCE_PRINCIPAL=true|' \
        "$DIR_CONFIG/.env"
    ok ".env criado a partir do .env.example"
    CONFIG_NOVA=1
fi
# O .env guarda o token do bot: legível apenas pelo dono.
sudo chown "$USUARIO:$USUARIO" "$DIR_CONFIG/.env"
sudo chmod 600 "$DIR_CONFIG/.env"

info "Preparando $DIR_ESTADO"
sudo mkdir -p "$DIR_ESTADO"
sudo chown "$USUARIO:$USUARIO" "$DIR_ESTADO"
ok "diretório de estado pronto"

# ── Serviço ──────────────────────────────────────────────────────────────
info "Instalando o serviço systemd"
sudo install -m 644 "$DESTINO/deploy/oci-relay.service" \
    "/etc/systemd/system/$SERVICO.service"
# A unit versionada assume o usuário 'ubuntu'; ajusta para quem instalou.
sudo sed -i "s|^User=.*|User=$USUARIO|; s|^Group=.*|Group=$USUARIO|; \
             s|^WorkingDirectory=.*|WorkingDirectory=$DESTINO|; \
             s|^ExecStart=.*|ExecStart=$DESTINO/.venv/bin/python -m oci_relay|" \
    "/etc/systemd/system/$SERVICO.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICO" >/dev/null 2>&1
ok "serviço instalado e habilitado no boot"

# ── Fim ──────────────────────────────────────────────────────────────────
echo
if [[ $CONFIG_NOVA -eq 1 ]]; then
    aviso "O serviço ainda NÃO foi iniciado: falta configurar as credenciais."
    echo
    echo "  1. Edite a configuração:"
    echo "       sudo nano $DIR_CONFIG/.env"
    echo
    echo "     Obrigatórios: TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_CHAT_IDS,"
    echo "                   OCI_REGION, OCI_INSTANCE_OCID"
    echo
    echo "  2. Crie o Dynamic Group e a policy no console (veja docs/SETUP.md)."
    echo "     Sem eles o Instance Principal falha e os comandos OCI não respondem."
    echo
    echo "  3. Inicie:"
    echo "       sudo systemctl start $SERVICO"
else
    info "Reiniciando o serviço"
    sudo systemctl restart "$SERVICO"
    ok "serviço reiniciado"
fi

echo
echo "  Acompanhar:  sudo journalctl -u $SERVICO -f"
echo "  Estado:      sudo systemctl status $SERVICO"
