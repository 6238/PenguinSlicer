// The page's side of the preview worker (src/preview/preview-client.js): a worker of its own for
// each sliced file, its progress passed on, its one reply the answer, the worker stopped once it
// has answered or when the page no longer wants the answer, and a worker that fails as a whole
// answering with the wizard's own report and one report to the server.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { prepareSlicedFile } from '../../src/preview/preview-client.js';
import { PREVIEW_FAILED } from '../../src/preview/preview-errors.js';
import { InThreadPreviewWorker } from '../fakes/preview-worker.js';
import { LAYERS, slicedOf } from './helpers.js';

function starter() {
  const started = [];
  return { started, start: () => { const w = new InThreadPreviewWorker(); started.push(w); return w.port; } };
}

test('a sliced file is prepared by a worker of its own, which is stopped once it has answered', async () => {
  const { started, start } = starter();
  const progress = [];
  const bytes = slicedOf(LAYERS);
  const job = prepareSlicedFile(start, bytes, null, { onProgress: (p) => progress.push(p.stage) });
  const answer = await job.done;
  assert.equal(answer.ok, true);
  assert.equal(answer.result.layers, 2);
  assert.equal(started.length, 1);
  assert.equal(started[0].terminated, true);
  assert.deepEqual([...new Set(progress)], ['unpacking', 'reading', 'preparing']);
  assert.equal(bytes.byteLength > 0, true, 'the page\'s bytes are copied to the worker, never taken from the page');
  assert.equal(started[0].posted[0].transfer.length, 0);
});

test('a preparation no longer wanted is stopped: its worker ends and its answer says so', async () => {
  const { started, start } = starter();
  const job = prepareSlicedFile(start, slicedOf(LAYERS), null);
  started[0].hold();
  job.stop();
  const answer = await job.done;
  assert.deepEqual(answer, { ok: false, stopped: true });
  assert.equal(started[0].terminated, true);
  await started[0].done;
  started[0].release();                                    // a reply after the stop changes nothing
});

test('a worker that fails as a whole answers with the wizard\'s report, sent once to the server', async () => {
  const { started, start } = starter();
  const reports = [];
  const job = prepareSlicedFile(start, slicedOf(LAYERS), null, { report: (what, fields) => reports.push([what, fields]) });
  started[0].hold();
  started[0].fail({ message: 'the script could not load' });
  const answer = await job.done;
  assert.equal(answer.ok, false);
  assert.equal(answer.error.code, PREVIEW_FAILED);
  assert.equal(answer.error.detail, 'the preview worker failed: the script could not load');
  assert.deepEqual(reports, [['page_failed', { detail: 'the preview worker failed: the script could not load' }]]);
  assert.equal(started[0].terminated, true);
});

test('a refusal of the worker is the answer, and its detail goes to the server once', async () => {
  const { start } = starter();
  const reports = [];
  const answer = await prepareSlicedFile(start, new TextEncoder().encode('words').buffer, null, { report: (what, f) => reports.push([what, f.detail]) }).done;
  assert.equal(answer.ok, false);
  assert.equal(answer.error.code, 'wizard.preview_unreadable');
  assert.deepEqual(reports, [['page_failed', 'wizard.preview_unreadable: The sliced file is not a zip archive (no end of its directory).']]);
});
