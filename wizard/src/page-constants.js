// The page's figures, as wizard/README-details.md "Constants" lists them, for the parts of the
// page built so far. The geometry's own figures are in geometry/constants.js. Every time is
// read through the clock seam, so a test moves it.

// The panel's widths (decision 6): each includes itself.
export const PANEL_MIN_PX = 320;
export const WIDTH_TABS_PX = 480;
export const WIDTH_FIGURES_PX = 520;
export const WIDTH_COLUMNS_PX = 680;

// The panel's own tooltip (decision 63).
export const TOOLTIP_DELAY_MS = 150;
export const TOOLTIP_EDGE_PX = 6;

// The panel line's passing use, when the user does not move ("a few seconds"; the mockup's 8).
export const PANEL_LINE_PASSING_S = 8;

// Retrying (the guide, "When the server is slow or cannot be reached").
export const ROW_SLOW_S = 4;
export const RETRY_QUIET_S = 20;
export const RETRY_TOTAL_S = 300;
export const RETRY_FIRST_WAIT_S = 1;
export const RETRY_MAX_WAIT_S = 30;
export const RETRY_SPREAD = 0.1;
export const ATTEMPT_TIMEOUT_S = 15;
export const UPLOAD_ATTEMPT_TIMEOUT_S = 60;
