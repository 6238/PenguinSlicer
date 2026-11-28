// The plate summary (decision 4): none on the Parts step; from the Settings step on, two lines,
// "1 part · 1 instance", then "PETG · Structural" and, while there are changes, the pill
// "+2 changes", which opens the change details: one plain line for each change.
import { CHANGES_PILL, CHANGES_PILL_TIP, PARTS_AND_INSTANCES } from '../sentences.js';

// One change's line: "Quality › Resolution: 0.014 mm (profile 0.012 mm)". The section and label
// come from the table of settings, or a quick change's own words where it has one.
export function changeLine({ section, label, value, profile }) {
  return `${section} › ${label}: ${value} (profile ${profile})`;
}

// What the summary shows on `step` for `plate`: {parts, instances, filament, filamentFull,
// profile, changes: [{section, label, value, profile}]}; null on the Parts step.
export function summaryModel(step, plate) {
  if (step === 'parts') return null;
  const count = plate.changes.length;
  return {
    first: PARTS_AND_INSTANCES(plate.parts, plate.instances),
    second: `${plate.filament} · ${plate.profile}`,
    secondFull: `${plate.filamentFull ?? plate.filament} · ${plate.profile}`,
    pill: count ? { text: CHANGES_PILL(count), tip: CHANGES_PILL_TIP(plate.profile), lines: plate.changes.map(changeLine) } : null,
  };
}
