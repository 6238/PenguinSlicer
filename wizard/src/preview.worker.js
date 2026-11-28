// The layer preview's worker: reads one sliced file and prepares what is drawn, so that nothing
// holds the page's main thread (wizard/README-details.md, "The layer preview"). Its message is
// that of preview/reading.js.
import { createPreviewReading } from './preview/reading.js';

const reading = createPreviewReading();

self.onmessage = async (event) => {
  const { reply, transfer } = await reading.handle(event.data, (message) => self.postMessage(message));
  self.postMessage(reply, transfer);
};
