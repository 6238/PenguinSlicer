// The failures of the layer preview, each an error report (contracts/error-report.md) of the
// wizard's own, so that the view hands its caller a report to show as it is, never a bare
// exception (wizard/README-details.md, "The layer preview"):
//   wizard.preview_unreadable     the sliced file cannot be read for drawing: not an archive, no
//                                 G-code, a G-code with no layers, a layer too tall to draw;
//   wizard.preview_failed         the preview's own code failed, or its worker did: a fault of
//                                 the page's own;
//   wizard.preview_not_drawable   the browser has no 3D drawing (WebGL 2) to draw it with.
// The sliced file itself is not in question in any of them, so each remedy keeps Download.

export const PREVIEW_UNREADABLE = 'wizard.preview_unreadable';
export const PREVIEW_FAILED = 'wizard.preview_failed';
export const PREVIEW_NOT_DRAWABLE = 'wizard.preview_not_drawable';

const SENTENCES = {
  [PREVIEW_UNREADABLE]: {
    message: 'PenguinSlicer could not read this plate\'s sliced file to draw its preview.',
    remedy: 'Slice the plate again; the sliced file can still be downloaded on the Send step.',
    retryable: false,
  },
  [PREVIEW_FAILED]: {
    message: 'PenguinSlicer could not draw the layer preview of this plate.',
    remedy: 'Reload the page; your parts, layout and settings are kept in this browser.',
    retryable: true,
  },
  [PREVIEW_NOT_DRAWABLE]: {
    message: 'This browser cannot draw the layer preview: its 3D drawing is turned off or missing.',
    remedy: 'Turn on hardware acceleration in the browser\'s settings, or use a current Chrome; the sliced file can still be downloaded on the Send step.',
    retryable: false,
  },
};

export function errorReport(code, detail) {
  return { code, ...SENTENCES[code], detail };
}

export class PreviewError extends Error {
  // `detail` is the evidence for the log: what exactly could not be read or drawn.
  constructor(detail, code = PREVIEW_UNREADABLE) {
    super(detail);
    this.name = 'PreviewError';
    this.report = errorReport(code, detail);
  }
}
