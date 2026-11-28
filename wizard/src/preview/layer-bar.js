// The layer bar's rules (wizard/README-details.md, "The result"; the mockup's js/wizard.js,
// setLayer): the keys that move it, where a pointer on it puts the layer, and its words. A layer
// is counted from 0 here and from 1 in every word a user reads. A layer's height is a printer's
// figure, always in millimetres, to a tenth, a trailing zero dropped as the mockup's lengths drop
// it ("3 mm", "40.2 mm").

export function clampLayer(k, layers) {
  return Math.max(0, Math.min(layers - 1, Math.round(k)));
}

// The layer a key takes the bar to from layer `k`, or null for a key the bar does not take.
export function layerForKey(key, k, layers) {
  const to = { ArrowUp: k + 1, ArrowRight: k + 1, ArrowDown: k - 1, ArrowLeft: k - 1, PageUp: k + 10, PageDown: k - 10, Home: 0, End: layers - 1 }[key];
  return to === undefined ? null : clampLayer(to, layers);
}

// The layer at `fraction` of the bar's height from its foot (0) to its top (1).
export function layerAtFraction(fraction, layers) {
  return clampLayer(fraction * (layers - 1), layers);
}

// How far up the bar layer `k` stands, 0 at the first layer and 1 at the last.
export function barFraction(k, layers) {
  return layers > 1 ? k / (layers - 1) : 1;
}

const mm = (z) => `${Math.round(z * 10) / 10} mm`;

// What the bar tells a screen reader.
export function valueText(k, layers, z) {
  return `Layer ${k + 1} of ${layers}, ${mm(z)} high`;
}

// The label beside the bar's thumb.
export function thumbLabel(k) {
  return `Layer ${k + 1}`;
}

// The readout under the view: "134 / 134 · 40.2 mm", one line even at 320 px.
export function readout(k, layers, z) {
  return `${k + 1} / ${layers} · ${mm(z)}`;
}
