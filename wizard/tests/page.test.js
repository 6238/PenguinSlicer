// The page's markup obeys the contract's rules for the wizard's built files: exactly one
// version placeholder, and nothing the content security policy forbids (no inline script,
// no style element or attribute, nothing loaded from another site). Each rule is a function
// that returns what breaks it, run on the real index.html and on pages that break it.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const INDEX = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'index.html');
const html = readFileSync(INDEX, 'utf8');
const VERSION_META = '<meta name="penguinslicer-version" content="__PENGUINSLICER_VERSION__">';

// Each src or href value, in double quotes, single quotes or none, as HTML allows.
const REFERENCE = /\s(?:src|href)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))/gi;
const OTHER_SITE = /^(?:[a-z][a-z0-9+.-]*:|\/\/)/i;

function placeholderCount(page) {
  return [page.split(VERSION_META).length - 1, page.split('__PENGUINSLICER_VERSION__').length - 1];
}

function inlineScripts(page) {
  const found = [];
  const scripts = [...page.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)];
  if (scripts.length === 0) found.push('the page loads no script');
  for (const [, attributes, body] of scripts) {
    if (!/\ssrc\s*=/i.test(attributes)) found.push(`a script without src: ${attributes}`);
    if (body.trim() !== '') found.push('a script with a body');
  }
  if (/\son[a-z]+\s*=/i.test(page)) found.push('an inline event handler');
  return found;
}

function styles(page) {
  const found = [];
  if (/<style\b/i.test(page)) found.push('a style element');
  if (/\sstyle\s*=/i.test(page)) found.push('a style attribute');
  return found;
}

function otherSites(page) {
  return [...page.matchAll(REFERENCE)].map((m) => m[1] ?? m[2] ?? m[3]).filter((v) => OTHER_SITE.test(v));
}

test('index.html carries the version placeholder exactly once', () => {
  assert.deepEqual(placeholderCount(html), [1, 1]);
});

test('a page with the placeholder twice, or none, is caught', () => {
  assert.deepEqual(placeholderCount(`${VERSION_META}${VERSION_META}`), [2, 2]);
  assert.deepEqual(placeholderCount('<html></html>'), [0, 0]);
});

test('index.html has no inline script', () => {
  assert.deepEqual(inlineScripts(html), []);
});

test('an inline script, a script without src and an event handler are caught', () => {
  assert.deepEqual(inlineScripts('<script src="a.js">go()</script>'), ['a script with a body']);
  assert.deepEqual(inlineScripts('<script type="module"></script>'), ['a script without src:  type="module"']);
  assert.deepEqual(inlineScripts('<script src=a.js></script><button onclick="go()">'), ['an inline event handler']);
  assert.deepEqual(inlineScripts('<html></html>'), ['the page loads no script']);
});

test('index.html has no style element or style attribute', () => {
  assert.deepEqual(styles(html), []);
});

test('a style element and a style attribute are caught', () => {
  assert.deepEqual(styles('<style>p{}</style>'), ['a style element']);
  assert.deepEqual(styles('<p style="color:red">'), ['a style attribute']);
  assert.deepEqual(styles("<p STYLE = 'color:red'>"), ['a style attribute']);
});

test('index.html loads nothing from another site', () => {
  assert.deepEqual(otherSites(html), []);
});

test('a reference to another site is caught in double quotes, single quotes or none', () => {
  assert.deepEqual(otherSites('<script src="https://cdn.example/a.js">'), ['https://cdn.example/a.js']);
  assert.deepEqual(otherSites("<script src='https://cdn.example/b.js'>"), ['https://cdn.example/b.js']);
  assert.deepEqual(otherSites('<script src=https://cdn.example/c.js>'), ['https://cdn.example/c.js']);
  assert.deepEqual(otherSites('<link HREF = //cdn.example/d.css>'), ['//cdn.example/d.css']);
  assert.deepEqual(otherSites('<script src="main.js"></script><a href="#steps">'), []);
});
