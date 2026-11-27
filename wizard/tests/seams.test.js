// The page reaches time and the network only through its seams: the clock, which a test
// moves, and the transport, which the fake front server replaces. A module that calls
// setTimeout, setInterval, Date.now or fetch directly would wait on the wall clock or the
// real network in a test, so this suite searches every page module for those names
// outside src/seams/ and fails naming each file and line.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

import { findForbidden, isSeam, pageModules, scanPage } from './forbidden_calls.js';

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', 'src');

test('no page module calls setTimeout, setInterval, Date.now or fetch outside the seams', () => {
  const found = scanPage(SRC);
  assert.deepEqual(found, [], found.map((f) => `${f.file}:${f.line} calls ${f.name}`).join('\n'));
});

test('the page has at least one module to search', () => {
  assert.ok(pageModules(SRC).length > 0, 'no .js module under wizard/src/');
});

test('each forbidden name is found, with its line', () => {
  const text = 'const a = 1;\nsetTimeout(f, 10);\nsetInterval(g, 5);\nconst t = Date.now();\nfetch("/api/me");\n';
  assert.deepEqual(findForbidden(text), [
    { name: 'setTimeout', line: 2 },
    { name: 'setInterval', line: 3 },
    { name: 'Date.now', line: 4 },
    { name: 'fetch', line: 5 },
  ]);
});

test('a name reached through the global object is found', () => {
  assert.deepEqual(findForbidden('window.setTimeout(f);').map((f) => f.name), ['setTimeout']);
  assert.deepEqual(findForbidden('globalThis.fetch(u);').map((f) => f.name), ['fetch']);
  assert.deepEqual(findForbidden('self["fetch"](u);').map((f) => f.name), ['fetch']);
  assert.deepEqual(findForbidden('const n = Date . now;').map((f) => f.name), ['Date.now']);
  assert.deepEqual(findForbidden('const { fetch: f } = globalThis;').map((f) => f.name), ['fetch']);
});

test('a name in a comment is not a call', () => {
  const text = '// setTimeout is not used here\n/* nor fetch,\n Date.now */ const x = 1;\n';
  assert.deepEqual(findForbidden(text), []);
});

test('a comment marker inside a string does not hide what follows it', () => {
  assert.deepEqual(findForbidden('const u = "http://x"; fetch(u);').map((f) => f.name), ['fetch']);
  assert.deepEqual(findForbidden("const u = '/*'; setTimeout(f); const v = '*/';").map((f) => f.name), ['setTimeout']);
  assert.deepEqual(findForbidden('const u = `//`; Date.now();').map((f) => f.name), ['Date.now']);
});

test('lines are counted across a block comment', () => {
  assert.deepEqual(findForbidden('/*\n\n*/\nfetch(u);'), [{ name: 'fetch', line: 4 }]);
});

test('words that only contain a name are not calls', () => {
  const text = 'prefetch(); fetchedParts; const setTimeoutMs = 3; Dates.now; myDate.nowish; clock.setTimer();';
  assert.deepEqual(findForbidden(text), []);
});

test('only files under seams/ are seams', () => {
  assert.equal(isSeam('seams/clock.js'), true);
  assert.equal(isSeam('seams/transport/fetch.js'), true);
  assert.equal(isSeam('clock.js'), false);
  assert.equal(isSeam('steps/seams/clock.js'), false);
  assert.equal(isSeam('seamsish/clock.js'), false);
});

test('a module outside the seams is reported and a seam is not', () => {
  const root = mkdtempSync(join(tmpdir(), 'wizard-seams-'));
  try {
    mkdirSync(join(root, 'seams'));
    mkdirSync(join(root, 'steps', 'deeper'), { recursive: true });
    writeFileSync(join(root, 'seams', 'clock.js'), 'export const now = () => Date.now();\n');
    writeFileSync(join(root, 'steps', 'deeper', 'parts.mjs'), 'export function go() {\n  setTimeout(go, 1);\n}\n');
    writeFileSync(join(root, 'main.js'), 'import "./steps/deeper/parts.mjs";\n');
    writeFileSync(join(root, 'notes.txt'), 'fetch\n');
    assert.deepEqual(scanPage(root), [{ file: 'steps/deeper/parts.mjs', line: 2, name: 'setTimeout' }]);
    assert.deepEqual(pageModules(root), ['main.js', 'seams/clock.js', 'steps/deeper/parts.mjs']);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
