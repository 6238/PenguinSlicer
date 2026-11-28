// The worker seam: the page's one worker, the second thread on which every heavy geometric job
// runs (wizard/README-details.md, "The geometry, in a worker"), behind a small port that the tests
// replace with the same messages run in their own thread (tests/fakes/worker.js).
//   post(message, transfer)       sends a message, transferring the buffers in `transfer`
//   listen(onReply, onFailure)    onReply(reply) for each reply; onFailure(error) when the worker
//                                 fails as a whole (its script cannot load, an error it did not
//                                 catch), after which it answers nothing more
export function geometryWorker() {
  const worker = new Worker(new URL('../geometry.worker.js', import.meta.url), { type: 'module' });
  return {
    post: (message, transfer = []) => worker.postMessage(message, transfer),
    listen(onReply, onFailure) {
      worker.onmessage = (event) => onReply(event.data);
      worker.onerror = (event) => { event.preventDefault(); onFailure({ message: event.message || 'the worker could not run' }); };
      worker.onmessageerror = () => onFailure({ message: 'a reply of the worker could not be read' });
    },
  };
}
