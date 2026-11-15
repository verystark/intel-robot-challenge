// Render the deck: the last frame of each slide (all animations done) → out/deck/slide_NN.png.
//   node scripts/deck.mjs        (npm run deck also makes the PDF)
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import path from 'node:path';
import fs from 'node:fs';

const SLIDE_FRAMES = 180; // keep in sync with src/deck/Deck.tsx
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const serveUrl = await bundle({entryPoint: path.join(root, 'src/index.ts')});
const composition = await selectComposition({serveUrl, id: 'Deck'});
const count = Math.round(composition.durationInFrames / SLIDE_FRAMES);
const out = path.join(root, 'out', 'deck');
fs.mkdirSync(out, {recursive: true});
for (const f of fs.readdirSync(out)) if (/^slide_\d+\.png$/.test(f)) fs.rmSync(path.join(out, f));
for (let i = 0; i < count; i++) {
  const output = path.join(out, `slide_${String(i + 1).padStart(2, '0')}.png`);
  await renderStill({serveUrl, composition, frame: i * SLIDE_FRAMES + SLIDE_FRAMES - 1, output, imageFormat: 'png'});
  console.log(output);
}
