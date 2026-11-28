// The sentences of the geometry's error reports are the guide's: every message and remedy a
// user reads is written, word for word, in wizard/README.md (wizard/README-details.md, "How to
// read this file": every sentence in quotation marks is copied from the guide).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { LAYOUT_FAILED, PART_NOT_DRAWABLE, errorReport } from '../../src/geometry/errors.js';
import { WIZARD } from './helpers.js';

const flat = (text) => text.replace(/\s+/g, ' ');
const guide = flat(readFileSync(join(WIZARD, 'README.md'), 'utf8'));
const details = flat(readFileSync(join(WIZARD, 'README-details.md'), 'utf8'));

for (const code of [PART_NOT_DRAWABLE, LAYOUT_FAILED]) {
  test(`${code}: its message and remedy are the guide's sentences, quoted the same in the details`, () => {
    const report = errorReport(code, 'what was wrong');
    for (const sentence of [report.message, report.remedy]) {
      assert.ok(guide.includes(`"${sentence}"`), `the guide does not quote ${JSON.stringify(sentence)}`);
      assert.ok(details.includes(`"${sentence}"`), `the details do not quote ${JSON.stringify(sentence)}`);
    }
  });
}
