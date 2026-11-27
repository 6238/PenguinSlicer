// The search behind tests/seams.test.js: which page modules name setTimeout, setInterval,
// Date.now or fetch outside the seams (wizard/src/seams/).
//
// Comments are not searched; strings and regular expression literals are, so that
// `globalThis['fetch']` is caught, and `Date['now']` is matched as Date.now. The scan knows
// strings, comments and regular expression literals (by the usual rule of thumb for telling a
// '/' that starts one from a division), not the rest of JavaScript. Building a name from pieces
// (`'set' + 'Timeout'`, `Date[n]`) escapes it; review catches that.
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

const FORBIDDEN = [
  ['setTimeout', /\bsetTimeout\b/g],
  ['setInterval', /\bsetInterval\b/g],
  ['Date.now', /\bDate\s*(?:\.\s*now\b|\[\s*(['"`])now\1\s*\])/g],
  ['fetch', /\bfetch\b/g],
];

const MODULE = /\.(?:js|mjs)$/;

// A '/' starts a regular expression literal, not a division, after one of these characters,
// after one of these words, or at the start of the text: the usual rule of thumb, since only
// a full parser knows for sure.
const BEFORE_REGEX = new Set('(,=:[!&|?{};+-*%<>~^'.split(''));
const WORD_BEFORE_REGEX = /(?:^|[^\w$])(?:return|typeof|instanceof|case|do|else|in|of|new|delete|void|throw|yield|await)$/;

function regexCanStart(out) {
  const before = out.trimEnd();
  return before === '' || BEFORE_REGEX.has(before[before.length - 1]) || WORD_BEFORE_REGEX.test(before);
}

// Where the regular expression literal opening at `start` ends (just after its closing '/'),
// or -1 when there is no closing '/' on the line, so it was not one.
function regexEnd(text, start) {
  let inClass = false;
  for (let i = start + 1; i < text.length; i += 1) {
    const c = text[i];
    if (c === '\n') return -1;
    if (c === '\\') { i += 1; continue; }
    if (c === '[') inClass = true;
    else if (c === ']') inClass = false;
    else if (c === '/' && !inClass) return i + 1;
  }
  return -1;
}

// The text with every comment replaced by spaces (newlines kept, so lines still count).
// Strings and regular expression literals are kept, so that the names in them are searched.
export function stripComments(text) {
  let out = '';
  let i = 0;
  while (i < text.length) {
    const c = text[i];
    const next = text[i + 1];
    const end = c === '/' && next !== '/' && next !== '*' && regexCanStart(out) ? regexEnd(text, i) : -1;
    if (end !== -1) {
      out += text.slice(i, end);
      i = end;
    } else if (c === '/' && next === '/') {
      while (i < text.length && text[i] !== '\n') { out += ' '; i += 1; }
    } else if (c === '/' && next === '*') {
      const end = text.indexOf('*/', i + 2);
      const stop = end === -1 ? text.length : end + 2;
      for (; i < stop; i += 1) out += text[i] === '\n' ? '\n' : ' ';
    } else if (c === '"' || c === "'" || c === '`') {
      out += c;
      i += 1;
      while (i < text.length && text[i] !== c) {
        if (text[i] === '\\' && i + 1 < text.length) { out += text[i]; i += 1; }
        out += text[i];
        i += 1;
      }
      if (i < text.length) { out += text[i]; i += 1; }
    } else {
      out += c;
      i += 1;
    }
  }
  return out;
}

// Each forbidden name in `text`, as {name, line}, in the order they appear.
export function findForbidden(text) {
  const code = stripComments(text);
  const found = [];
  for (const [name, pattern] of FORBIDDEN) {
    for (const match of code.matchAll(pattern)) {
      found.push({ name, index: match.index });
    }
  }
  found.sort((a, b) => a.index - b.index);
  return found.map(({ name, index }) => ({ name, line: code.slice(0, index).split('\n').length }));
}

// Whether a module, named by its path relative to src/ with '/' between folders, is a seam.
export function isSeam(path) {
  return path.startsWith('seams/');
}

// Every module under `root`, as paths relative to it with '/' between folders, sorted.
export function pageModules(root) {
  const modules = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) walk(path);
      else if (MODULE.test(entry.name)) modules.push(relative(root, path).split(sep).join('/'));
    }
  };
  walk(root);
  return modules.sort();
}

// Each forbidden name in a module under `root` that is not a seam, as {file, line, name}.
export function scanPage(root) {
  const found = [];
  for (const file of pageModules(root)) {
    if (isSeam(file)) continue;
    for (const { name, line } of findForbidden(readFileSync(join(root, file), 'utf8'))) {
      found.push({ file, line, name });
    }
  }
  return found;
}
