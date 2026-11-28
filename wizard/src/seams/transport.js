// The transport seam: the one place the page reaches the network. The module that makes every
// request (api.js) takes a transport with this shape, and the tests give it the fake front
// server (tests/fakes/front_server.js), which answers, holds, drops or repeats each request in
// the order a test sets.
//   send({method, path, headers, body, signal}) resolves to an answer
//     {status, header(name), json(), text(), bytes()} once the answer's headers arrive, and
//     rejects when the connection fails or `signal` aborts it.
// Requests go to the page's own address only: `path` is a path such as "/api/me", and the
// browser attaches the cookie, which the page never reads.
export const fetchTransport = {
  async send({ method, path, headers, body, signal }) {
    const response = await fetch(path, {
      method, headers, body, signal, credentials: 'same-origin', cache: 'no-store',
    });
    return {
      status: response.status,
      header: (name) => response.headers.get(name),
      json: () => response.json(),
      text: () => response.text(),
      bytes: () => response.arrayBuffer(),
    };
  },
};
