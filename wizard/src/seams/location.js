// The location seam: the page's own reload for a new version (wizard/README-details.md,
// "Reloading for a new version"), behind one function that the tests replace.
export function reloadPage(location = globalThis.location) {
  location.reload();
}

// The sign-in trip (signing-in.js): the page's own address, its path and query, and the
// navigation to /signin.
export function pageAddress(location = globalThis.location) {
  return `${location.pathname}${location.search}`;
}

export function goTo(address, location = globalThis.location) {
  location.assign(address);
}
