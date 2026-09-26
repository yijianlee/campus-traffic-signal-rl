// The loader must deduplicate requests, survive rapid switches and allow retries.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const requests = [];
const context = {
  window: {},
  document: {
    createElement: () => ({ remove() {} }),
    head: { append: script => requests.push(script) },
  },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname, '../traffic_rl/web/scripts/loader.js'), 'utf8'), context);
const entry = key => ({ key, src: key + '.js' });
function complete(key) {
  context.window.TRAFFIC_CHUNKS[key] = { frames: [{ t: 0 }], key };
  requests.findLast(script => script.src === key + '.js').onload();
}
(async () => {
  const loader = context.window.ReplayLoader;
  const first = loader.load(entry('a')), duplicate = loader.load(entry('a'));
  assert.equal(requests.length, 1);
  complete('a');
  assert.equal(await first, await duplicate);
  const second = loader.load(entry('b')), third = loader.load(entry('c'));
  complete('b'); complete('c');
  assert.equal((await second).key, 'b'); assert.equal((await third).key, 'c');
  assert.equal(Object.keys(context.window.TRAFFIC_CHUNKS).length, 2);
  const failed = loader.load(entry('missing'));
  requests.at(-1).onerror();
  await assert.rejects(failed, /无法读取/);
  const retry = loader.load(entry('missing')); complete('missing');
  assert.equal((await retry).key, 'missing');
  console.log('Replay loader: duplicate requests, bounded cache, concurrent loads and retry passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
