// The figures the geometry uses, as wizard/README-details.md, "Constants", lists them. The names
// MAX_*, MARGIN_MM and SPACING_* are the plate configuration's contract's; the others are the
// wizard's own (proposed there, settled here).

// One part (contracts/plate-configuration.md, "Limits").
export const MAX_PART_BYTES = 7500084;
export const MAX_PART_TRIANGLES = 150000;
export const MAX_INSTANCES = 150;

// The placement rules (the same).
export const MARGIN_MM = 3;
export const SPACING_MM = 5;
export const SPACING_SUPPORTS_MM = 12;
// The slice service decides each rule with this tolerance, and so does the wizard.
export const EPS_MM = 1e-6;

// Finding the faces a part can lie on.
export const FACE_JOIN_DEG = 0.06;      // hull triangles joined into one flat face
export const MIN_FACE_MM2 = 5;          // a face smaller than this is dropped
export const MAX_FACES = 254;           // all but the largest this many are dropped
export const SLIVER_DEG = 1;            // a face with a corner sharper than this is dropped
export const ROUND_SIDE_DEG = 20;       // a facet among its like bends less than this from a neighbour
export const BBOX_COVER_DEG = 30.5;     // 30 degrees, plus half a degree for rounding
// What lies on a face: within this distance of its plane and this angle of its direction. A
// thin strip of the hull that lies on a larger face's plane is part of that face; a triangle of
// the part that lies on a hull face is the part's own surface there, not a bridge.
export const FLAT_GAP_MM = 0.01;
export const FLAT_TURN_DEG = 1;
// A corner within this distance of the hull is on it, not outside it. Far below the rounding
// of a single-precision STL coordinate, so that no corner of the hull is lost: a tolerance of
// 1e-3 mm, tried first, left a corner of Clamp Plate Inner 0.006 mm outside its hull and
// corners of a test sphere 0.012 mm outside, too near the 0.01 mm by which the placement
// checks must agree. Small enough flats come
// out as several hull triangles, which joining into faces puts back together.
export const HULL_EPS_MM = 1e-6;

// A hull face is not offered when the part laid on it would rest on no face of its own: the slice
// service's rule for slice.rests_on_an_edge (slice/README-details.md, "Error codes"), with its
// figures, so that the wizard offers no hull face the slice service would refuse for it with the
// default first layer (bounding-box patches are not tested; wizard/README-details.md). The
// part's own faces on the plate (triangles with every corner within ON_THE_PLATE_MM of it) add
// up to less than REST_AREA_MM2, and its section half a first layer above the plate holds no
// line of the first layer (no disc FIRST_LINE_MM across fits in it); the first layer is the
// default process's, FIRST_LAYER_MM tall.
export const REST_AREA_MM2 = 0.01;
export const ON_THE_PLATE_MM = 1e-3;
export const FIRST_LAYER_MM = 0.3;
export const FIRST_LINE_MM = 0.62;

// Auto-orient.
export const MIN_CONTACT_MM2 = 25;      // a resting candidate counts only with this much touching
export const CONTACT_GAP_MM = 0.1;      // a triangle this close to the plate touches it
export const OVERHANG_DEG = 45;         // a downward face steeper than this from vertical hangs over air
export const HEIGHT_CHARGE_PER_MM = 0.01;   // the small charge for height
export const NO_CONTACT_PENALTY = 100;  // the large penalty when almost nothing touches
export const AS_MODELLED_MARGIN = 0.05; // as modelled is kept when within this share of the best cost

// Arrange.
export const PILE_GRID_MM = 5;
export const PILE_REFINE_MM = 1;
// Arrange leaves this much more than the spacing between outlines, so that a plate it
// arranges passes the placement check by more than the check's rounding.
export const ARRANGE_SLACK_MM = 0.05;
// Arrange's map of the plate is in squares this wide; each outline it marks may take up to
// about one square's diagonal more room than it needs.
export const ARRANGE_CELL_MM = 0.5;
