// Render a few still frames to check the layout without rendering the whole video.
//   node scripts/stills.mjs [seconds ...]     (default: one frame in each scene)
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import path from 'node:path';
import fs from 'node:fs';

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const serveUrl = await bundle({entryPoint: path.join(root, 'src/index.ts')});
const composition = await selectComposition({serveUrl, id: 'Jenssenit'});
const fps = composition.fps;
const seconds = process.argv.slice(2).map(Number);
const times = seconds.length ? seconds : [4, 16, 30, 43, 52, 62, 104, 113, 118];
const out = path.join(root, 'out', 'stills');
fs.mkdirSync(out, {recursive: true});
for (const s of times) {
  const frame = Math.min(Math.round(s * fps), composition.durationInFrames - 1);
  const output = path.join(out, `t${String(s).padStart(5, '0')}.jpg`);
  await renderStill({serveUrl, composition, frame, output, imageFormat: 'jpeg', jpegQuality: 85});
  console.log(output);
}
console.log(`duration ${(composition.durationInFrames / fps).toFixed(1)} s`);
