// Regrava .glb exportados pelo Blender (modelos_celular.py): o Godot 4.7 recusa alguns JPEGs que o Blender grava
// (bloco de metadados APP1) e tenta abrir como PNG ("Not a PNG file" / "Couldn't load image"), ficando sem a
// textura. Aqui cada JPEG é recodificado limpo (sharp) e o mimeType fica escrito.
// Uso: node regravar_glb.mjs arquivo1.glb arquivo2.glb ...   (npm i sharp @gltf-transform/core@4 @gltf-transform/extensions@4)
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import sharp from 'sharp';
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
for (const f of process.argv.slice(2)) {
  const d = await io.read(f);
  for (const t of d.getRoot().listTextures()) {
    const b = t.getImage();
    if (b[0] === 0x89) { t.setMimeType('image/png'); continue; }
    t.setImage(new Uint8Array(await sharp(b).jpeg({ quality: 90 }).toBuffer()));
    t.setMimeType('image/jpeg');
  }
  await io.write(f, d);
  console.log('regravado', f.split('/').pop());
}
