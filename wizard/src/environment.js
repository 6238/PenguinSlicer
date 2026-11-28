// What the page knows of its browser: the random ids it makes, and what its reports about itself
// say of the browser (wizard/README-details.md, "What the wizard reports about itself").

// A random version 4 UUID: a plate's plate_id, the page's id for its reports. Made from the
// browser's random bytes, which every browser gives a page, also one not served over HTTPS (where
// crypto.randomUUID is missing).
export function randomId(fill = (array) => globalThis.crypto.getRandomValues(array)) {
  const b = fill(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const hex = [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

const BRANDS = [['Microsoft Edge', 'Edge'], ['Google Chrome', 'Chrome'], ['Chromium', 'Chrome']];
const AGENTS = [[/Edg\/([\d.]+)/, 'Edge'], [/(?:Headless)?Chrome\/([\d.]+)/, 'Chrome'], [/Firefox\/([\d.]+)/, 'Firefox'], [/Version\/([\d.]+).*Safari/, 'Safari']];

// The browser's name and version, as the browser gives them: its brands where it has them,
// otherwise its user agent.
export function browserOf(navigator) {
  const brands = navigator && navigator.userAgentData && navigator.userAgentData.brands;
  if (Array.isArray(brands)) {
    for (const [brand, name] of BRANDS) {
      const found = brands.find((b) => b.brand === brand);
      if (found) return { browser: name, browser_version: String(found.version) };
    }
  }
  const agent = navigator && typeof navigator.userAgent === 'string' ? navigator.userAgent : '';
  for (const [pattern, name] of AGENTS) {
    const match = agent.match(pattern);
    if (match) return { browser: name, browser_version: match[1] };
  }
  return { browser: 'unknown', browser_version: 'unknown' };
}

// Whether the browser draws 3D in software: a WebGL context asked to fail on a major performance
// caveat is refused where drawing is in software (SwiftShader on a machine without a graphics
// card). Asked once, when the first report needs it; the context is given back at once.
export function softwareDrawing(makeCanvas = () => globalThis.document.createElement('canvas')) {
  try {
    const gl = makeCanvas().getContext('webgl2', { failIfMajorPerformanceCaveat: true });
    if (!gl) return true;
    const lose = gl.getExtension('WEBGL_lose_context');
    if (lose) lose.loseContext();
    return false;
  } catch {
    return true;
  }
}

// The environment the reports module reads.
export function browserEnvironment(navigator = globalThis.navigator) {
  const { browser, browser_version: version } = browserOf(navigator);
  let software = null;
  return {
    browser,
    browser_version: version,
    software_3d: () => { if (software === null) software = softwareDrawing(); return software; },
  };
}
