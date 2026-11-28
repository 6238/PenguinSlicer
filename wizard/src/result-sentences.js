// The words of a sliced plate's result on the Preview step and of the Send step in phase 2
// (wizard/README-details.md, "The result", "The layer preview", "The Send step"). Every figure
// comes from the sliced file's details; these are the words around them.

// The two large figures and the quiet line under them (decision 33).
export const PRINT_TIME = 'Print time';
export const FILAMENT = 'Filament';
export const GRAMS = (g) => `${Math.round(g)} g`;
export const GRAMS_OF = (g, filament) => `${GRAMS(g)} ${filament}`;
export const INSTANCES = (n) => `${n} instance${n === 1 ? '' : 's'}`;
export const LAYERS = (n) => `${n} layer${n === 1 ? '' : 's'}`;
export const SLICED_IN = (time) => `sliced in ${time}`;
export const QUIET_SEPARATOR = ' · ';

// Under the layer preview: the two small buttons, Reset view, the "?" and its sentence.
export const LAYER_DOWN = 'One layer down';
export const LAYER_UP = 'One layer up';
export const RESET_VIEW = 'Reset view';
export const HELP_LABEL = 'How to move the view';
export const HELP = 'Drag to turn, right-drag to pan, scroll to zoom; drag the bar on the right to go through the layers.';

// The colour key at the view's top left: always all four rows, in the four fixed colours.
export const KEY_LABEL = 'Colour key';
export const KEY = [
  { label: 'Walls', colour: '#2b5c9e' },
  { label: 'Infill', colour: '#e0912f' },
  { label: 'Top and bottom surfaces', colour: '#2f9e7a' },
  { label: 'Supports and brim', colour: '#9a8fb8' },
];

// The Send step's card of what will be printed (decision 35), with no printer in phase 2.
export const SEND_INSTANCES = 'Instances';
export const ON_ONE_PLATE = (n) => `${n} on one plate`;
export const OF_PART = (count, name) => (count > 1 ? `${count} × ${name}` : name);
export const OF_FILAMENT = (filament) => ` of ${filament}`;
export const DOWNLOAD = 'Download the sliced file';

// The notification Download leaves: the plate in words and the file's true size (fake 11, the
// plate named by what it holds, never numbered).
export const DOWNLOADED = (instances, size) => `Downloaded the sliced file of ${INSTANCES(instances)} (${size}).`;
// The same when the details give no size, which the contract always gives.
export const DOWNLOADED_NO_SIZE = (instances) => `Downloaded the sliced file of ${INSTANCES(instances)}.`;
