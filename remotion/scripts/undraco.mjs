// Decode a Draco-compressed glTF/GLB into a plain one (for Blender builds that ship without the Draco library).
//   node scripts/undraco.mjs in.glb out.glb
import {NodeIO} from '@gltf-transform/core';
import {ALL_EXTENSIONS, KHRDracoMeshCompression} from '@gltf-transform/extensions';
import draco3d from 'draco3dgltf';

const [, , src, dst] = process.argv;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({'draco3d.decoder': await draco3d.createDecoderModule()});
const doc = await io.read(src);
for (const ext of doc.getRoot().listExtensionsUsed()) if (ext instanceof KHRDracoMeshCompression) ext.dispose();
await io.write(dst, doc);
