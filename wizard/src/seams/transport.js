// The transport seam: the one place the page reaches the network. The module that makes every
// request (api.js) takes a transport with this shape, and the tests give it the fake front
// server (tests/fakes/front_server.js), which answers, holds, drops or repeats each request in
// the order a test sets.
//   send({method, path, headers, body, signal}) resolves to an answer
//     {status, header(name), json(), text(onProgress), bytes(onProgress)} once the answer's
//     headers arrive, and rejects when the connection fails or `signal` aborts it. text and
//     bytes read the whole body, calling onProgress(byteCount) each time bytes arrive, so that
//     the caller can tell a body that is arriving slowly from one that has stalled.
// Requests go to the page's own address only: `path` is a path such as "/api/me", and the
// browser attaches the cookie, which the page never reads.
// Reads a response's whole body into one ArrayBuffer, telling onProgress of each part.
export async function readBody(response, onProgress) {
  if (!response.body) return new ArrayBuffer(0);
  const reader = response.body.getReader();
  const parts = [];
  let length = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    parts.push(value);
    length += value.byteLength;
    if (onProgress) onProgress(value.byteLength);
  }
  const whole = new Uint8Array(length);
  let at = 0;
  for (const part of parts) { whole.set(part, at); at += part.byteLength; }
  return whole.buffer;
}

export const fetchTransport = {
  async send({ method, path, headers, body, signal }) {
    const response = await fetch(path, {
      method, headers, body, signal, credentials: 'same-origin', cache: 'no-store',
    });
    return {
      status: response.status,
      header: (name) => response.headers.get(name),
      json: () => response.json(),
      text: async (onProgress) => new TextDecoder().decode(await readBody(response, onProgress)),
      bytes: (onProgress) => readBody(response, onProgress),
    };
  },
};
