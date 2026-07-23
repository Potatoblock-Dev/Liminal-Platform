/**
 * 将 net 入口打成 IIFE，写入 app/games/liminal_platform/static/js/。
 * 不 emptyOutDir，避免删掉尚未迁到 TS 的其它脚本。
 */
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { build, createLogger } from 'vite';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const outDir = path.resolve(root, 'app/games/liminal_platform/static/js');
const watch = process.argv.includes('--watch');

const entries = [
  {
    name: 'lp-network',
    entry: path.resolve(root, 'client/src/entries/lp-network.ts'),
    globalName: 'LiminalNetworkBundle',
  },
  {
    name: 'lp-session',
    entry: path.resolve(root, 'client/src/entries/lp-session.ts'),
    globalName: 'LiminalSessionBundle',
  },
];

const logger = createLogger();

async function buildOne({ name, entry, globalName }) {
  await build({
    configFile: false,
    root,
    logLevel: 'info',
    customLogger: logger,
    build: {
      outDir,
      emptyOutDir: false,
      sourcemap: true,
      target: 'es2020',
      lib: {
        entry,
        name: globalName,
        formats: ['iife'],
        fileName: () => `${name}.js`,
      },
      rollupOptions: {
        output: {
          inlineDynamicImports: true,
          extend: true,
        },
      },
      watch: watch ? {} : null,
    },
  });
}

for (const entry of entries) {
  await buildOne(entry);
  if (!watch) {
    console.log(`built ${entry.name}.js`);
  }
}

if (watch) {
  console.log('watching client entries…');
}
