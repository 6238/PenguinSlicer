// The preview worker seam: a worker of its own for each sliced file the layer preview reads, the
// second thread on which the file is read and prepared (wizard/README-details.md, "The layer
// preview"), behind a small port that the tests replace with the same messages run in their own
// thread (tests/fakes/preview-worker.js).
//   post(message, transfer)       sends a message
//   listen(onMessage, onFailure)  onMessage(message) for each progress report and the reply;
//                                 onFailure(error) when the worker fails as a whole (its script
//                                 cannot load, an error it did not catch)
//   terminate()                   stops the worker and gives back its memory
export function startPreviewWorker() {
  const worker = new Worker(new URL('../preview.worker.js', import.meta.url), { type: 'module' });
  return {
    post: (message, transfer = []) => worker.postMessage(message, transfer),
    listen(onMessage, onFailure) {
      worker.onmessage = (event) => onMessage(event.data);
      worker.onerror = (event) => { event.preventDefault(); onFailure({ message: event.message || 'the worker could not run' }); };
      worker.onmessageerror = () => onFailure({ message: 'a message of the worker could not be read' });
    },
    terminate: () => worker.terminate(),
  };
}
