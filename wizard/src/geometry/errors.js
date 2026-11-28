// The failures the geometry can meet, each an error report (contracts/error-report.md) from the
// start, so that the worker hands the main thread a report it shows as a notification, never a
// bare exception:
//   wizard.part_not_drawable  a part the geometry cannot read, measure or lay out (a malformed
//                             STL, a part that is flat or encloses nothing);
//   wizard.layout_failed      the page asked the worker for something it cannot do (a part it
//                             was never given, a message it does not know), or the layout code
//                             failed: a fault of the page's own.

export const PART_NOT_DRAWABLE = 'wizard.part_not_drawable';
export const LAYOUT_FAILED = 'wizard.layout_failed';

const SENTENCES = {
  [PART_NOT_DRAWABLE]: {
    message: 'PenguinSlicer could not show this part, so it cannot be imported.',
    remedy: 'Export the part again as a binary STL and add it again.',
    retryable: false,
  },
  [LAYOUT_FAILED]: {
    message: 'PenguinSlicer could not work out the layout of this plate.',
    remedy: 'Reload the page; your parts, layout and settings are kept in this browser.',
    retryable: true,
  },
};

export function errorReport(code, detail) {
  return { code, ...SENTENCES[code], detail };
}

export class GeometryError extends Error {
  // `detail` is the evidence for the log: what exactly was wrong with the file.
  constructor(detail, code = PART_NOT_DRAWABLE) {
    super(detail);
    this.name = 'GeometryError';
    this.report = errorReport(code, detail);
  }
}
