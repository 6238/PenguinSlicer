// The page's entry point. Until the skeleton is built it only reads the page's version from
// its <meta>, which the front server fills in, and marks the document as started, so that
// the browser tests can see the page's code ran under the content security policy.
const meta = document.querySelector('meta[name="penguinslicer-version"]');
document.documentElement.dataset.version = meta ? meta.content : '';
document.documentElement.dataset.started = 'true';
