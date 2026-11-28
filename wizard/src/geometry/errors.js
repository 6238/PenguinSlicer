// The one failure the geometry can meet: a part it cannot read, measure or lay out. It is an
// error report (contracts/error-report.md) from the start, so the worker hands the main thread
// a report it shows as a notification, never a bare exception.

export const PART_NOT_DRAWABLE = 'wizard.part_not_drawable';

const MESSAGE = 'PenguinSlicer could not show this part, so it cannot be imported.';
const REMEDY = 'Export the part again as a binary STL and add it again.';

export class GeometryError extends Error {
  // `detail` is the evidence for the log: what exactly was wrong with the file.
  constructor(detail) {
    super(detail);
    this.name = 'GeometryError';
    this.report = { code: PART_NOT_DRAWABLE, message: MESSAGE, remedy: REMEDY, retryable: false, detail };
  }
}
