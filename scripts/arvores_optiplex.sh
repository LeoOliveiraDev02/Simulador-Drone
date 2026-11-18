#!/bin/bash
# Árvores leves para o pacote do OptiPlex (Intel HD Graphics 2500): 30 a 100 mil triângulos cada
# (com 0.015 o eucalipto perdia as folhas e virava galho com pontinhos pretos; 0.032 = ~66 mil)
# (o original do Poly Haven tem 1 a 4 milhões). Usa o gltfpack no modo agressivo (-sa), que mantém a
# copa cheia melhor que o Decimate do Blender e não estoura a memória no jacarandá (3,9 milhões).
# Saída em recursos/modelos_movel/ (o mapa usa essa pasta no celular e no modo OptiPlex).
# Depois devolve o alphaMode das folhas (optiplex/copiar_alpha.mjs; precisa de @gltf-transform/core e extensions
# no node_modules da PASTA_NODE).
# Uso: scripts/arvores_optiplex.sh PASTA_RECURSOS PASTA_NODE   (npm i gltfpack @gltf-transform/core@4 @gltf-transform/extensions@4)
set -e
REC="$(realpath "$1")"; NODE="$(realpath "$2")"; GP="$NODE/node_modules/.bin/gltfpack"
cp "$(dirname "$0")/optiplex/copiar_alpha.mjs" "$NODE/"
mkdir -p "$REC/modelos_movel"
for par in island_tree_01:0.035 island_tree_02:0.035 island_tree_03:0.03 tree_small_02:0.032 jacaranda_tree:0.03; do
  n="${par%%:*}"; r="${par#*:}"
  "$GP" -i "$REC/modelos/$n/${n}_1k.gltf" -o "$REC/modelos_movel/$n.glb" -si "$r" -sa -noq -kn -km
  node "$NODE/copiar_alpha.mjs" "$REC/modelos/$n/${n}_1k.gltf" "$REC/modelos_movel/$n.glb"
  echo "ok $n"
done
