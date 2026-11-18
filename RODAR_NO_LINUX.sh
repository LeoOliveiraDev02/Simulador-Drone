#!/bin/bash
# ============================================================================
#  SIMULADORES DO LEONARDO — RODAR NO LINUX (PCs do IF Baiano, Ubuntu)
#  Feito para o Dell OptiPlex 7010 (Intel HD Graphics 2500, Ubuntu 26.04).
#
#  COMO USAR (só isto):
#    1. Coloque este arquivo na MESMA pasta do SimuladorDrone-OptiPlex.zip
#       (pode ser no pendrive ou em Downloads).
#    2. Abra o Terminal (Ctrl+Alt+T), digite  bash  e um espaço,
#       ARRASTE este arquivo para dentro do Terminal e aperte Enter.
#  Na primeira vez ele copia tudo para a sua pasta pessoal (~/SimuladorDrone),
#  prepara as texturas (alguns minutos) e cria um atalho no menu de aplicativos
#  e na Área de Trabalho. Depois é só abrir pelo atalho.
#
#  Por que antes não abria: rodando direto do pendrive o Linux não deixa
#  executar programas (sem permissão de execução), e dar dois cliques num .sh
#  abre o editor de texto em vez de rodar. Este arquivo resolve as duas coisas.
# ============================================================================

DEST="$HOME/SimuladorDrone"
LINK_MONTAPC="https://claude.ai/artifact/W42AAQwkyo21JuUQ36dsGZ"
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$DEST"
LOG="$DEST/rodar.log"
exec > >(tee -a "$LOG") 2>&1
echo
echo "===== $(date '+%d/%m/%Y %H:%M:%S') ====="

pausa() { echo; read -r -p "Aperte Enter para fechar." _; }

# ---------------------------------------------------------------- escolha
OPCAO="${1:-}"
if [ -z "$OPCAO" ]; then
  if command -v zenity >/dev/null 2>&1 && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
    OPCAO=$(zenity --list --title="Simuladores" --text="O que você quer abrir?" \
      --column="n" --column="Simulador" --hide-column=1 --width=420 --height=260 \
      1 "Simulador de Drone — voo do E88" \
      2 "Monta PC em Libras — versão leve (navegador)" 2>/dev/null)
  fi
  if [ -z "$OPCAO" ]; then
    echo "O que você quer abrir?"
    echo "  1) Simulador de Drone — voo do E88"
    echo "  2) Monta PC em Libras — versão leve (abre no navegador)"
    read -r -p "Digite 1 ou 2 e aperte Enter: " OPCAO
  fi
fi

if [ "$OPCAO" = "2" ]; then
  echo "Abrindo o Monta PC em Libras (versão leve) no navegador..."
  OFF=$(find "$AQUI" "$HOME/Downloads" -maxdepth 2 -iname "*monta*pc*offline*.html" 2>/dev/null | head -n1)
  if [ -n "$OFF" ]; then
    xdg-open "$OFF" >/dev/null 2>&1 &
  else
    xdg-open "$LINK_MONTAPC" >/dev/null 2>&1 &
  fi
  sleep 2
  exit 0
fi

# ---------------------------------------------------------------- instalar o drone
achar_base() {
  B=$(find "$DEST" -maxdepth 3 -name "VOAR_E88_OPTIPLEX.sh" 2>/dev/null | head -n1)
  [ -n "$B" ] && dirname "$B"
}

BASE="$(achar_base)"
if [ -z "$BASE" ]; then
  ZIP=$(find "$AQUI" "$HOME/Downloads" "$HOME" -maxdepth 2 -iname "SimuladorDrone-OptiPlex*.zip" 2>/dev/null | head -n1)
  if [ -z "$ZIP" ]; then
    echo "Não achei o SimuladorDrone-OptiPlex.zip."
    echo "Coloque o zip na mesma pasta deste arquivo (ou em Downloads) e rode de novo."
    pausa; exit 1
  fi
  LIVRE=$(df -Pm "$HOME" | awk 'NR==2{print $4}')
  if [ "${LIVRE:-0}" -lt 1200 ]; then
    echo "Pouco espaço na pasta pessoal (${LIVRE} MB livres; precisa de uns 1,2 GB)."
    pausa; exit 1
  fi
  echo "Copiando e extraindo o simulador para $DEST (só na primeira vez)..."
  if command -v unzip >/dev/null 2>&1; then
    unzip -q -o "$ZIP" -d "$DEST" || { echo "Falhou ao extrair com unzip."; pausa; exit 1; }
  else
    python3 -m zipfile -e "$ZIP" "$DEST" || { echo "Falhou ao extrair (sem unzip e sem python3?)."; pausa; exit 1; }
  fi
  BASE="$(achar_base)"
  [ -z "$BASE" ] && { echo "O zip não tem o VOAR_E88_OPTIPLEX.sh — pacote incompleto."; pausa; exit 1; }
fi
cd "$BASE" || exit 1

G="$(find "$BASE" -maxdepth 2 -name 'Godot_v*linux.x86_64' | head -n1)"
if [ -z "$G" ]; then
  echo "Não achei o programa do Godot dentro de $BASE."
  pausa; exit 1
fi
chmod +x "$G" "$BASE"/*.sh 2>/dev/null

# zip novo do jogo ao lado (atualização)
if [ -f "$BASE/voo_e88_optiplex.zip" ]; then
  echo "Instalando a versão nova do voo do E88..."
  python3 -m zipfile -e voo_e88_optiplex.zip . && mv -f voo_e88_optiplex.zip voo_e88_optiplex_instalado.zip
  rm -rf voo_e88/.godot/imported
fi

if [ ! -d voo_e88/.godot/imported ]; then
  echo
  echo "Preparando modelos e texturas para a placa de vídeo (só na primeira vez, alguns minutos)..."
  "$G" --headless --path voo_e88 --import
fi

# ---------------------------------------------------------------- atalho
criar_atalho() {
  local ARQ="$HOME/.local/share/applications/simulador-drone.desktop"
  mkdir -p "$(dirname "$ARQ")"
  cat > "$ARQ" <<EOF
[Desktop Entry]
Type=Application
Name=Simulador de Drone (E88)
Comment=Voo do E88 — modo OptiPlex
Exec=bash "$BASE/RODAR_NO_LINUX.sh" 1
Icon=$BASE/voo_e88/icone.png
Terminal=true
Categories=Game;
EOF
  chmod +x "$ARQ"
  local MESA
  MESA="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Área de Trabalho")"
  if [ -d "$MESA" ]; then
    cp -f "$ARQ" "$MESA/"
    chmod +x "$MESA/simulador-drone.desktop"
    gio set "$MESA/simulador-drone.desktop" metadata::trusted true 2>/dev/null
  fi
}
cp -f "$0" "$BASE/RODAR_NO_LINUX.sh" 2>/dev/null
criar_atalho

# ---------------------------------------------------------------- abrir
echo "Abrindo o voo do E88 (modo OptiPlex: OpenGL + FSR 1)..."
tentar() {
  local INI=$SECONDS
  "$@"
  local RC=$?
  # fechou sozinho em menos de 8 s com erro = não conseguiu abrir
  if [ $RC -ne 0 ] && [ $((SECONDS - INI)) -lt 8 ]; then return 1; fi
  return 0
}
ARGS=(--path voo_e88 --rendering-method gl_compatibility --rendering-driver opengl3)
tentar "$G" "${ARGS[@]}" -- --optiplex && exit 0
echo "Não abriu do jeito normal; tentando pela janela X11..."
tentar "$G" "${ARGS[@]}" --display-driver x11 -- --optiplex && exit 0
echo "Ainda não abriu; tentando com o vídeo por software (vai ficar lento, mas abre)..."
LIBGL_ALWAYS_SOFTWARE=1 tentar "$G" "${ARGS[@]}" --display-driver x11 -- --optiplex --grafico=0 && exit 0

echo
echo "Não consegui abrir. Mande para o Claude o arquivo: $LOG"
pausa
exit 1
