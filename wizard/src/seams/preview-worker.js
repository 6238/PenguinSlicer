// The preview worker seam: a worker of its own for each sliced file the layer preview reads, the
// second thread on which the file is read and prepared (wizard/README-details.md, "The layer
// preview"), behind a small port that the tests replace with the same messages run in their own
// thread (tests/fakes/preview-worker.js).
//   post(message, transfer)       sends a message
//   listen(onMessage, onFailure)  onMessage(message) for each progress report and the reply;
//                                 onFailure(error) when the worker fails as a whole (its script
//                                 cannot load, an error it did not catch)
//   terminate()                   stops the worker and gives back its memory
//
// The page fetches every file of its own code when it loads and nothing later by name, since a
// deploy replaces the page files (contracts/wizard-front-server.md, "A page loaded before a
// deploy"). So one worker is started when the page loads (warmPreviewWorker), its code fetched
// then, and kept idle until a sliced file is shown; each worker taken starts the next one at once,
// whose code the browser then has in its cache under the same names. What a worker says before it
// is listened to (a script that could not load) is kept for its listener.
const url = () => new URL('../preview.worker.js', import.meta.url);

function launch() {
  const worker = new Worker(url(), { type: 'module' });
  const early = [];
  let onMessage = null;
  let onFailure = null;
  const fail = (error) => { if (onFailure) onFailure(error); else early.push(['failure', error]); };
  worker.onmessage = (event) => { if (onMessage) onMessage(event.data); else early.push(['message', event.data]); };
  worker.onerror = (event) => { event.preventDefault(); fail({ message: event.message || 'the worker could not run' }); };
  worker.onmessageerror = () => fail({ message: 'a message of the worker could not be read' });
  return {
    post: (message, transfer = []) => worker.postMessage(message, transfer),
    listen(message, failure) {
      onMessage = message;
      onFailure = failure;
      for (const [kind, value] of early.splice(0)) (kind === 'message' ? onMessage : onFailure)(value);
    },
    terminate: () => worker.terminate(),
  };
}

let spare = null;

// Starts the spare worker, so that its code is fetched while the page loads.
export function warmPreviewWorker() {
  if (!spare) spare = launch();
}

export function startPreviewWorker() {
  const port = spare ?? launch();
  spare = launch();
  return port;
}
