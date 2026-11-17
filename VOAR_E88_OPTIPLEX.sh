#!/bin/bash
# Simulador de Drone - voo do E88 no modo OptiPlex (Linux, vídeo integrado antigo, ex.: Intel HD Graphics 2500)
# Usa o renderizador de Compatibilidade (OpenGL), o mapa leve e o FSR 1 feito à mão.
cd "$(dirname "$0")" || exit 1
G="./Godot/Godot_v4.7.2-stable_linux.x86_64"
if [ ! -f "$G" ]; then
  echo "Não achei o Godot em $G (ele vem junto no pacote do OptiPlex)."
  read -r -p "Aperte Enter para fechar." _
  exit 1
fi
chmod +x "$G"

# instala (ou atualiza) o projeto quando chega um zip novo ao lado deste arquivo
if [ -f voo_e88_optiplex.zip ]; then
  echo "Instalando a versão nova do voo do E88..."
  unzip -q -o voo_e88_optiplex.zip && mv -f voo_e88_optiplex.zip voo_e88_optiplex_instalado.zip
  rm -rf voo_e88/.godot/imported
fi

if [ ! -d voo_e88/.godot/imported ]; then
  echo
  echo "Preparando os modelos e texturas para a placa de vídeo."
  echo "Isso só acontece na primeira vez e leva alguns minutos..."
  "$G" --headless --path voo_e88 --import
fi

echo "Abrindo o voo do E88 (modo OptiPlex: OpenGL + FSR 1)..."
exec "$G" --path voo_e88 --rendering-method gl_compatibility --rendering-driver opengl3 -- --optiplex "$@"
