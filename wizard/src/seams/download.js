// The download seam: the one place the page has the browser save a file from the front server, by
// a plain link, so that the browser saves it without the page holding it (wizard/README-details.md,
// "The Send step", Download). A test replaces it to see what would be saved.
//   saveLink(href, name)   the browser saves the answer to `href`, offered under `name`
export function saveLink(href, name) {
  const link = document.createElement('a');
  link.href = href;
  link.download = name;
  link.rel = 'noopener';
  link.hidden = true;
  document.body.append(link);
  link.click();
  link.remove();
}
