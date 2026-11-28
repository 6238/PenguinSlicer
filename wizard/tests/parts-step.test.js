// The Parts step's drawing that needs no browser window (src/panel/parts-step.js): how a warning's
// sentences are split into the two lines of the amber message on its row (wizard/README-details.md,
// "Uploading a part"). The rest of the drawing is tested in Chromium (tests_browser/test_parts_step.py).
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { firstSentence } from '../src/panel/parts-step.js';

test('a warning splits after its first sentence, the words unchanged', () => {
  assert.deepEqual(
    firstSentence('This part is not watertight: its mesh has 14 open edges in 2 places. It may still slice and print. If the slice fails, look again.'),
    ['This part is not watertight: its mesh has 14 open edges in 2 places.', 'It may still slice and print. If the slice fails, look again.'],
  );
  assert.deepEqual(firstSentence('Is it in inches? Every side is under 5 mm.'), ['Is it in inches?', 'Every side is under 5 mm.']);
});

test('a warning of one sentence is one line', () => {
  assert.deepEqual(firstSentence('This part is inside out.'), ['This part is inside out.', null]);
  assert.deepEqual(firstSentence('No full stop at all'), ['No full stop at all', null]);
});

test('a full stop inside a sentence, as in an abbreviation or a figure, does not end it', () => {
  assert.deepEqual(
    firstSentence('Some faces point inwards, e.g. on the hub. Export it again.'),
    ['Some faces point inwards, e.g. on the hub.', 'Export it again.'],
  );
  assert.deepEqual(firstSentence('Every side is under 5 mm, i.e. 0.2 in. Check the units.'), ['Every side is under 5 mm, i.e. 0.2 in.', 'Check the units.']);
});
