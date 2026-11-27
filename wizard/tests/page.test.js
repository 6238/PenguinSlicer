// The page's markup obeys the contract's rules for the wizard's built files: exactly one
// version placeholder, and nothing the content security policy forbids (no inline script,
// no style element or attribute, nothing loaded from another site).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const INDEX = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'index.html');
const html = readFileSync(INDEX, 'utf8');
const VERSION_META = '<meta name="penguinslicer-version" content="__PENGUINSLICER_VERSION__">';

test('index.html carries the version placeholder exactly once', () => {
  assert.equal(html.split(VERSION_META).length - 1, 1);
  assert.equal(html.split('__PENGUINSLICER_VERSION__').length - 1, 1);
});

test('index.html has no inline script', () => {
  const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)];
  assert.ok(scripts.length > 0, 'the page loads no script');
  for (const [, attributes, body] of scripts) {
    assert.match(attributes, /\bsrc="/, `a script without src: ${attributes}`);
    assert.equal(body.trim(), '', 'a script with a body');
  }
  assert.doesNotMatch(html, /\son[a-z]+\s*=/i, 'an inline event handler');
});

test('index.html has no style element or style attribute', () => {
  assert.doesNotMatch(html, /<style\b/i);
  assert.doesNotMatch(html, /\sstyle\s*=/i);
});

test('index.html loads nothing from another site', () => {
  for (const [, value] of html.matchAll(/\s(?:src|href)="([^"]*)"/gi)) {
    assert.doesNotMatch(value, /^(?:[a-z][a-z0-9+.-]*:|\/\/)/i, `loads ${value}`);
  }
});
