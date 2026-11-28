// The worker: the second thread on which every heavy geometric job runs, so that nothing holds
// the page's main thread (wizard/README-details.md, "The geometry, in a worker"). Its messages
// are those of geometry/messages.js.
import { createGeometry } from './geometry/messages.js';

const geometry = createGeometry();

self.onmessage = (event) => {
  const { reply, transfer } = geometry.handle(event.data);
  self.postMessage(reply, transfer);
};
