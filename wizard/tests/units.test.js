// A part's size in its own units (src/units.js; wizard/README-details.md, "Units"): inches to
// three decimals, millimetres to 0.1 mm, rounded once from the exact millimetres; and a file's
// size in megabytes for the notification of a part over the size limit.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { formatSize, megabytes } from '../src/units.js';

test('a part in inches reads in inches to three decimals, from the exact millimetres', () => {
  assert.equal(formatSize([50.8, 50.8, 4.775], 'in'), '2.000 × 2.000 × 0.188 in');
  assert.equal(formatSize([6.35, 25.4, 0.1], 'in'), '0.250 × 1.000 × 0.004 in');
});

test('a part in millimetres reads in millimetres to 0.1 mm, without a trailing zero', () => {
  assert.equal(formatSize([50.8, 50, 4.775], 'mm'), '50.8 × 50 × 4.8 mm');
  assert.equal(formatSize([0.04, 340, 12.25], 'mm'), '0 × 340 × 12.3 mm');
});

test('units other than the two are a fault of the page', () => {
  assert.throws(() => formatSize([1, 1, 1], 'cm'), /units/);
});

test('a file\'s size is in megabytes of a million bytes, rounded up to 0.1, so a refused file never reads as the limit', () => {
  assert.equal(megabytes(9_100_000), '9.1');
  assert.equal(megabytes(9_100_001), '9.2');
  assert.equal(megabytes(7_500_085), '7.6');
  assert.equal(megabytes(12_000_000), '12.0');
});
