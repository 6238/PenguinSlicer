// A small fake of the document, enough for a step's module (src/panel/*-step.js) to be built and
// driven on Node, with no browser: each element answers querySelector with a child of its own for
// each selector, made the first time it is asked for, so a step's markup need not be written out.
// It draws nothing and checks no markup: the browser tests do that. installDocument() puts it where
// telling.js's `el` finds it, as `document`.

class FakeClassList {
  constructor() { this.names = new Set(); }
  toggle(name, on) { if (on ?? !this.names.has(name)) this.names.add(name); else this.names.delete(name); }
  add(name) { this.names.add(name); }
  remove(name) { this.names.delete(name); }
  contains(name) { return this.names.has(name); }
}

export class FakeElement {
  constructor(doc, tag = 'div') {
    this.ownerDocument = doc;
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.found = new Map();
    this.listeners = new Map();
    this.attributes = new Map();
    this.classList = new FakeClassList();
    this.style = {};
    this.textContent = '';
    this.className = '';
    this.hidden = false;
    this.disabled = false;
    this.title = '';
  }

  querySelector(selector) {
    if (!this.found.has(selector)) this.found.set(selector, new FakeElement(this.ownerDocument));
    return this.found.get(selector);
  }

  querySelectorAll() { return []; }
  get firstChild() { return this.children[0] ?? null; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = [...nodes]; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(listener);
  }
  focus() {}
  scrollIntoView() {}
}

export class FakeDocument extends FakeElement {
  constructor() {
    super(null, '#document');
    this.ownerDocument = this;
  }

  createElement(tag) { return new FakeElement(this, tag); }
  createTextNode(text) { return { textContent: String(text) }; }
}

// A fake document set as the global `document`, and a section element of it.
export function installDocument() {
  const doc = new FakeDocument();
  globalThis.document = doc;
  return { doc, section: doc.createElement('section') };
}
