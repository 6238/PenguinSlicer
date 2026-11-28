// The location seam: the page's own reload for a new version (wizard/README-details.md,
// "Reloading for a new version"), behind one function that the tests replace.
export function reloadPage(location = globalThis.location) {
  location.reload();
}
