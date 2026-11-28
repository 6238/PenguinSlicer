// The page's side of the preview worker (wizard/README-details.md, "The layer preview"): a worker
// of its own for each sliced file, started through the preview worker seam, so that reading and
// preparing a file of up to 50 MB never holds the main thread, and stopped as soon as it has
// answered, which gives back its memory. The bytes and the parts' corners are copied to it,
// never transferred: the page keeps its own.
import { PREVIEW_FAILED, errorReport } from './preview-errors.js';

// prepareSlicedFile(startWorker, bytes, plate, {onProgress, report}):
//   startWorker()  a port of the seam's shape ({post, listen(onMessage, onFailure), terminate})
//   bytes          the sliced file, an ArrayBuffer
//   plate          {instances, meshes} for the ghost, or null
//   onProgress({stage, fraction})  each progress report of the worker
//   report(what, {detail})         a report about the page itself: `page_failed` once, when the
//                                  file cannot be prepared
// Returns {done, stop}: `done` resolves to {ok: true, result} (reading.js), {ok: false, error}
// with an error report, or {ok: false, stopped: true} once `stop()` was called first.
export function prepareSlicedFile(startWorker, bytes, plate, { onProgress = () => {}, report = () => {} } = {}) {
  const port = startWorker();
  let finish;
  const done = new Promise((resolve) => { finish = resolve; });
  let over = false;
  const end = (answer) => {
    if (over) return;
    over = true;
    port.terminate();
    if (!answer.ok && answer.error) report('page_failed', { detail: answer.error.code === PREVIEW_FAILED ? answer.error.detail : `${answer.error.code}: ${answer.error.detail}` });
    finish(answer);
  };
  port.listen((message) => {
    if (over) return;
    if (message.progress) { onProgress(message.progress); return; }
    end(message.ok ? { ok: true, result: message.result } : { ok: false, error: message.error });
  }, (failure) => {
    end({ ok: false, error: errorReport(PREVIEW_FAILED, `the preview worker failed: ${failure && failure.message ? failure.message : String(failure)}`) });
  });
  port.post({ id: 1, op: 'prepare', bytes, plate });
  return {
    done,
    stop() {
      if (over) return;
      over = true;
      port.terminate();
      finish({ ok: false, stopped: true });
    },
  };
}
