// Units (wizard/README-details.md, "Units"): a part's size in its own units, rounded once from the
// exact millimetres in the unit shown, by this one function on every step, so that a part has one
// size everywhere; inches to three decimals ("2.000 × 2.000 × 0.188 in"), millimetres to 0.1 mm.
const MM_PER_INCH = 25.4;

export function formatSize(sizeMm, units) {
  if (units === 'in') return `${sizeMm.map((mm) => (mm / MM_PER_INCH).toFixed(3)).join(' × ')} in`;
  if (units === 'mm') return `${sizeMm.map((mm) => String(Number(mm.toFixed(1)))).join(' × ')} mm`;
  throw new Error(`units must be "mm" or "in", not ${JSON.stringify(units)}`);
}

// A file's size in megabytes of a million bytes, to 0.1 MB, rounded up so that a file over the
// limit never reads as the limit itself ("7.6 MB" for 7,500,085 bytes, the limit being 7.5 MB).
export function megabytes(bytes) {
  return (Math.ceil(bytes / 100_000) / 10).toFixed(1);
}
