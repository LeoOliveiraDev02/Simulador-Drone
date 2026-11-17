// gltfpack troca alphaMode BLEND -> OPAQUE quando a textura não tem transparência.
// O mapa (mapa.gd, _ajustar_folhas) só põe o shader das folhas quando o material é transparente,
// então devolve o alphaMode/alphaCutoff do .gltf original para cada material com o mesmo nome.
// Uso: node copiar_alpha.mjs original.gltf reduzida.glb
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { readFileSync } from 'fs';
const [orig, glb] = process.argv.slice(2);
const mats = Object.fromEntries(JSON.parse(readFileSync(orig, 'utf8')).materials.map((m) => [m.name, m]));
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
const doc = await io.read(glb);
for (const m of doc.getRoot().listMaterials()) {
  const o = mats[m.getName()];
  if (!o || !o.alphaMode) continue;
  m.setAlphaMode(o.alphaMode);
  if (o.alphaCutoff !== undefined) m.setAlphaCutoff(o.alphaCutoff);
  console.log(glb.split('/').pop(), m.getName(), '->', o.alphaMode);
}
await io.write(glb, doc);
