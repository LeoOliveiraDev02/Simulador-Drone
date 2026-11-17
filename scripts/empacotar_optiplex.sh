#!/bin/bash
# Monta o pacote do voo do E88 para o OptiPlex (Linux, Intel HD Graphics 2500): SimuladorDrone-OptiPlex.zip
#
# Uso: scripts/empacotar_optiplex.sh PASTA_RECURSOS GODOT_LINUX PASTA_NODE SAIDA.zip
#   PASTA_RECURSOS  recursos do mapa (voo_e88_recursos.zip extraído + scripts/baixar_recursos.py para o que faltar)
#   GODOT_LINUX     Godot_v4.7.2-stable_linux.x86_64 (github.com/godotengine/godot/releases)
#   PASTA_NODE      node_modules com gltfpack, sharp, @gltf-transform/core@4 e @gltf-transform/extensions@4
#   Precisa do Blender (blender no PATH ou "pip install bpy") para as plantas e pedras leves.
#
# O que muda em relação ao pacote do PC (só neste pacote; os recursos não ficam no Git):
#   - recursos/modelos_movel: plantas e pedras leves (blender/modelos_celular.py) e árvores ainda mais leves
#     pelo gltfpack (scripts/arvores_optiplex.sh); JPEGs do Blender regravados (optiplex/regravar_glb.mjs)
#   - texturas com compressão de vídeo (S3TC) e mipmaps (antes: sem compressão e sem mipmaps)
#   - sem os originais das árvores, arbustos e pedras (1 a 4 milhões de triângulos; o modo OptiPlex não usa)
#   - sem a pasta .godot: o VOAR_E88_OPTIPLEX.sh prepara tudo na primeira vez que abre
set -e
AQUI="$(cd "$(dirname "$0")/.." && pwd)"
REC="$(realpath "$1")"; GODOT="$(realpath "$2")"; NODE="$(realpath "$3")"; SAIDA="$(realpath -m "$4")"
TMP="$(mktemp -d)"; P="$TMP/SimuladorDrone-OptiPlex"
mkdir -p "$P/Godot"
cp "$GODOT" "$P/Godot/Godot_v4.7.2-stable_linux.x86_64"
cp -r "$AQUI/voo_e88" "$P/voo_e88"
rm -rf "$P/voo_e88/.godot" "$P/voo_e88/prints" "$P/voo_e88/recursos"
cp -r "$REC" "$P/voo_e88/recursos"

# plantas e pedras leves (Blender) + árvores mais leves (gltfpack) + JPEGs regravados
# (um processo por modelo: o Blender cai sem memória nas árvores gigantes, que vêm do gltfpack)
mkdir -p "$TMP/blender_saida"
for d in "$P"/voo_e88/recursos/modelos/*/; do
  n="$(basename "$d")"
  case "$n" in *tree_0*|tree_small_02|jacaranda_tree) continue ;; esac
  mkdir -p "$TMP/um_$n" && ln -s "$d" "$TMP/um_$n/$n"
  if command -v blender >/dev/null; then
    blender -b -P "$AQUI/blender/modelos_celular.py" -- "$TMP/um_$n" "$TMP/blender_saida" || echo "falhou $n"
  else
    python3 "$AQUI/blender/modelos_celular.py" -- "$TMP/um_$n" "$TMP/blender_saida" || echo "falhou $n"
  fi
done
mkdir -p "$P/voo_e88/recursos/modelos_movel"
cp "$TMP"/blender_saida/*.glb "$P/voo_e88/recursos/modelos_movel/" 2>/dev/null || true
"$AQUI/scripts/arvores_optiplex.sh" "$P/voo_e88/recursos" "$NODE"
cp "$AQUI/scripts/optiplex/regravar_glb.mjs" "$NODE/"
for f in "$P"/voo_e88/recursos/modelos_movel/*.glb; do
  case "$(basename "$f")" in island_tree_*|tree_small_02*|jacaranda_tree*) ;; *) node "$NODE/regravar_glb.mjs" "$f" ;; esac
done

# texturas: compressão de vídeo + mipmaps (a HD 2500 divide a memória com o sistema)
python3 - "$P/voo_e88/recursos" <<'EOF'
import re, sys, pathlib
for p in pathlib.Path(sys.argv[1]).rglob('*.import'):
    if not re.search(r'\.(jpg|jpeg|png)\.import$', p.name):
        continue
    s = p.read_text()
    if 'importer="texture"' not in s:
        continue
    s = re.sub(r'compress/mode=\d', 'compress/mode=2', s)
    s = re.sub(r'mipmaps/generate=\w+', 'mipmaps/generate=true', s)
    s = re.sub(r'detect_3d/compress_to=\d', 'detect_3d/compress_to=0', s)
    p.write_text(s)
EOF

# originais pesados que o modo OptiPlex não carrega (ficam só os usados por _cena_simples)
for n in island_tree_01 island_tree_02 island_tree_03 tree_small_02 jacaranda_tree shrub_01 shrub_02 shrub_04 \
         boulder_01 rock_07 stone_01 modular_wooden_pier grass_medium_01; do
  rm -rf "$P/voo_e88/recursos/modelos/$n"
done

cp "$AQUI/VOAR_E88_OPTIPLEX.sh" "$AQUI/COMO_VOAR_NO_OPTIPLEX.txt" "$AQUI/COMO_VOAR_E88.txt" "$P/"
chmod +x "$P/VOAR_E88_OPTIPLEX.sh" "$P/Godot/Godot_v4.7.2-stable_linux.x86_64"
rm -f "$SAIDA"
(cd "$TMP" && zip -q -r -9 "$SAIDA" SimuladorDrone-OptiPlex)
rm -rf "$TMP"
ls -la "$SAIDA"
