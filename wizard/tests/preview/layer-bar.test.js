// The layer bar's rules (src/preview/layer-bar.js; wizard/README-details.md, "The result" and
// "The layer preview"): the keys that move it, where a pointer on it puts the layer, what it tells
// a screen reader, and the readout's words, in millimetres.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { barFraction, clampLayer, layerAtFraction, layerForKey, readout, thumbLabel, valueText } from '../../src/preview/layer-bar.js';

test('the arrow keys step one layer, Page Up and Page Down ten, Home and End go to the ends', () => {
  const n = 134;
  assert.equal(layerForKey('ArrowUp', 50, n), 51);
  assert.equal(layerForKey('ArrowRight', 50, n), 51);
  assert.equal(layerForKey('ArrowDown', 50, n), 49);
  assert.equal(layerForKey('ArrowLeft', 50, n), 49);
  assert.equal(layerForKey('PageUp', 50, n), 60);
  assert.equal(layerForKey('PageDown', 50, n), 40);
  assert.equal(layerForKey('Home', 50, n), 0);
  assert.equal(layerForKey('End', 50, n), 133);
  assert.equal(layerForKey('a', 50, n), null, 'another key does nothing to the bar');
});

test('the layer never leaves the plate\'s layers', () => {
  assert.equal(layerForKey('ArrowUp', 133, 134), 133);
  assert.equal(layerForKey('PageDown', 3, 134), 0);
  assert.equal(clampLayer(-4, 10), 0);
  assert.equal(clampLayer(12.6, 10), 9);
  assert.equal(clampLayer(4.4, 10), 4);
});

test('the bar runs from the first layer at its foot to the last at its top', () => {
  assert.equal(layerAtFraction(0, 134), 0);
  assert.equal(layerAtFraction(1, 134), 133);
  assert.equal(layerAtFraction(0.5, 134), 67);
  assert.equal(layerAtFraction(1.7, 134), 133);
  assert.equal(barFraction(133, 134), 1);
  assert.equal(barFraction(0, 134), 0);
  assert.equal(barFraction(0, 1), 1, 'a plate of one layer shows it whole');
});

test('the bar tells a screen reader its layer and its height; the readout is in millimetres, on one line', () => {
  assert.equal(valueText(133, 134, 40.2), 'Layer 134 of 134, 40.2 mm high');
  assert.equal(thumbLabel(133), 'Layer 134');
  assert.equal(readout(133, 134, 40.2), '134 / 134 · 40.2 mm');
  assert.equal(readout(0, 13, 0.2), '1 / 13 · 0.2 mm');
  assert.equal(readout(171, 344, 41.34000015258789), '172 / 344 · 41.3 mm');
});

test('a whole millimetre drops its trailing zero, as the mockup\'s lengths do', () => {
  assert.equal(readout(14, 15, 3.0), '15 / 15 · 3 mm');
  assert.equal(readout(14, 15, 2.96), '15 / 15 · 3 mm');
  assert.equal(valueText(14, 15, 3.0), 'Layer 15 of 15, 3 mm high');
  assert.equal(readout(0, 15, 0.04), '1 / 15 · 0 mm');
});
