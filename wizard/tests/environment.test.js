// What the page knows of its browser (src/environment.js): the random ids it makes (a plate's
// plate_id, the page's id for its reports), and the browser's name and version for its reports.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { browserEnvironment, browserOf, graphicsCard, osOf, randomId, softwareDrawing } from '../src/environment.js';

test('a random id is a version 4 UUID, of the contract\'s form for a plate_id, and new each time', () => {
  const ids = new Set();
  for (let i = 0; i < 50; i += 1) {
    const id = randomId();
    assert.match(id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    assert.match(id, /^[A-Za-z0-9_-]{1,64}$/);
    ids.add(id);
  }
  assert.equal(ids.size, 50);
});

test('a random id is made from the bytes it is given', () => {
  const bytes = (array) => { array.fill(0xff); return array; };
  assert.equal(randomId(bytes), 'ffffffff-ffff-4fff-bfff-ffffffffffff');
});

test('the browser\'s name and version come from its brands, Chrome first, or else from its user agent', () => {
  assert.deepEqual(browserOf({ userAgentData: { brands: [{ brand: 'Not A(Brand', version: '99' }, { brand: 'Chromium', version: '131' }, { brand: 'Google Chrome', version: '131' }] }, userAgent: '' }),
    { browser: 'Chrome', browser_version: '131' });
  assert.deepEqual(browserOf({ userAgentData: { brands: [{ brand: 'Chromium', version: '131' }, { brand: 'Microsoft Edge', version: '131' }] }, userAgent: '' }),
    { browser: 'Edge', browser_version: '131' });
  assert.deepEqual(browserOf({ userAgent: 'Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/131.0.6778.33 Safari/537.36' }),
    { browser: 'Chrome', browser_version: '131.0.6778.33' });
  assert.deepEqual(browserOf({ userAgent: 'Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0' }),
    { browser: 'Firefox', browser_version: '133.0' });
  assert.deepEqual(browserOf({ userAgent: 'something else' }), { browser: 'unknown', browser_version: 'unknown' });
  assert.deepEqual(browserOf(undefined), { browser: 'unknown', browser_version: 'unknown' });
});

test('the operating system comes from the browser\'s platform, or else from its user agent', () => {
  assert.equal(osOf({ userAgentData: { platform: 'macOS' }, userAgent: '' }), 'macOS');
  assert.equal(osOf({ userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36' }), 'macOS');
  assert.equal(osOf({ userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }), 'Windows');
  assert.equal(osOf({ userAgent: 'Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36' }), 'ChromeOS');
  assert.equal(osOf({ userAgent: 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36' }), 'Android');
  assert.equal(osOf({ userAgent: 'Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36' }), 'Linux');
  assert.equal(osOf({ userAgent: 'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X)' }), 'iOS');
  assert.equal(osOf({ userAgent: 'something else' }), 'unknown');
  assert.equal(osOf(undefined), 'unknown');
});

test('the graphics card is the renderer the browser names, or null when it names none', () => {
  const gl = (ext) => ({ getExtension: (n) => (n === 'WEBGL_debug_renderer_info' ? ext : null), getParameter: (p) => (p === 0x9246 ? 'ANGLE (Apple, ANGLE Metal Renderer: Apple M2, Unspecified Version)' : 'WebKit WebGL') });
  assert.equal(graphicsCard(() => ({ getContext: () => gl({ UNMASKED_RENDERER_WEBGL: 0x9246 }) })), 'ANGLE (Apple, ANGLE Metal Renderer: Apple M2, Unspecified Version)');
  assert.equal(graphicsCard(() => ({ getContext: () => gl(null) })), 'WebKit WebGL', 'the masked renderer when the browser gives no other');
  assert.equal(graphicsCard(() => ({ getContext: () => null })), null);
  assert.equal(graphicsCard(() => { throw new Error('no canvas'); }), null);
});

test('the machine\'s figures for a drawing summary: processors and memory as the browser reports them, the panel inside Onshape by its address', () => {
  const env = browserEnvironment(
    { userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/131.0.0.0', hardwareConcurrency: 8, deviceMemory: 8 },
    { search: '?in=onshape&documentId=1', devicePixelRatio: 2, panelWidth: () => 360 },
  );
  assert.equal(env.os, 'macOS');
  assert.equal(env.processors, 8);
  assert.equal(env.memory_gb, 8);
  assert.equal(env.in_onshape, true);
  assert.equal(env.pixel_ratio(), 2);
  assert.equal(env.panel_width_px(), 360);
  const tab = browserEnvironment({ userAgent: '' }, { search: '', devicePixelRatio: undefined, panelWidth: () => 0 });
  assert.equal(tab.in_onshape, false);
  assert.equal(tab.processors, undefined);
  assert.equal(tab.memory_gb, undefined);
  assert.equal(tab.pixel_ratio(), 1);
});

test('drawing in software is told by a context that refuses a major performance caveat', () => {
  const canvas = (hardware) => ({ getContext: (kind, options) => (options && options.failIfMajorPerformanceCaveat && !hardware ? null : { getExtension: () => null }) });
  assert.equal(softwareDrawing(() => canvas(false)), true);
  assert.equal(softwareDrawing(() => canvas(true)), false);
  assert.equal(softwareDrawing(() => { throw new Error('no canvas'); }), true);
});
