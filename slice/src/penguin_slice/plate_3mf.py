"""The plate as a 3MF Orca slices without moving anything, and the checks on what it sliced.

One <object> per instance, never one object shared by several build items: Orca blanks
the names of instances that share an object, and the names are what the printer's
skip-object list shows and what the name guard below reads back. Each object holds its
part's mesh in part coordinates; its build item carries instance_matrix (plate.py) in 3MF's row-vector
order. Orca drops every part to the bed and, with --arrange 0, keeps x, y and rotation.
The objects are written part by part, so Orca lists them grouped by part; the name guard
compares names in any order.
"""
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import quoteattr

from .mesh import read_binary_stl
from .plate import instance_labels, instance_matrix, sanitize_part_name
from .slicer import ARCHIVE_SUFFIX, SliceCancelled, SliceError

MODEL_ENTRY = "3D/3dmodel.model"
LOCAL_TIME_RE = re.compile(r'^\d{8}-\d{4}$')
LEFT_OFF_MESSAGE = "A part was left off the plate."
PART_GONE_MESSAGE = "The file for {name} is missing."

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
"""
RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""
MODEL_HEAD = ('<?xml version="1.0" encoding="UTF-8"?>\n'
              '<model unit="millimeter" xml:lang="en-US" '
              'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">\n<resources>\n')


def _mesh_xml(stl_path, name):
    """The part's <mesh> element as bytes: de-duplicated vertices (%.4f) and faces. A file
    that went away after the plate configuration was checked is a SliceError (slice.part_missing)."""
    try:
        data = Path(stl_path).read_bytes()
    except OSError as exc:
        raise SliceError(PART_GONE_MESSAGE.format(name=name), f"{stl_path}: {exc}", error_code="slice.part_missing",
                         where={"part": name}) from None
    mesh = read_binary_stl(data, name, source=str(stl_path))
    vertices = "".join('<vertex x="%.4f" y="%.4f" z="%.4f"/>' % tuple(v) for v in mesh.vertices.tolist())
    triangles = "".join('<triangle v1="%d" v2="%d" v3="%d"/>' % tuple(f) for f in mesh.faces.tolist())
    return f"<mesh><vertices>{vertices}</vertices><triangles>{triangles}</triangles></mesh>".encode("ascii")


def _transform(instance, footprint):
    """instance_matrix as 3MF's twelve numbers: M's columns, then the translation."""
    m = instance_matrix(instance['orientation'], instance['angle'], footprint['offset'], instance['x'],
                        instance['y'])
    order = [m[r][c] for c in range(3) for r in range(3)] + [m[0][3], m[1][3], m[2][3]]
    return " ".join("%.9g" % (value + 0.0) for value in order)


def _check_stop(stop):
    """Raise SliceCancelled when the slice job's stop is set (a cancel, an abandonment, a
    shutdown): the write ends here and Orca is never started."""
    if stop is not None and stop.is_set():
        raise SliceCancelled(f"stopped by the slice service ({stop.reason}) while the plate was being written, "
                             "before Orca was started")


def write_plate_3mf(path, instances, parts, stop=None):
    """Write the plate's 3MF to `path` and return its object names, one per instance.

    `instances` are {'ref', 'orientation', 'angle', 'x', 'y'}; `parts[ref]` carries `name`,
    `stl_path` and `footprints`. Each part's STL is read once. The objects are written part
    by part, every instance of a part after its mesh is built, so only one part's mesh text
    is held at a time; object ids and build items keep the instances' order. `stop` (a
    slicer.Stop) is looked at before each part's mesh and each object: once it is set the
    write raises SliceCancelled, within one object's write of the stop.
    """
    names = instance_labels([parts[instance['ref']]['name'] for instance in instances])
    object_ids = {}                       # ref -> the object ids of its instances, in first-use order
    for object_id, instance in enumerate(instances, start=1):
        object_ids.setdefault(instance['ref'], []).append(object_id)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES)
        zf.writestr("_rels/.rels", RELS)
        with zf.open(MODEL_ENTRY, "w") as model:
            model.write(MODEL_HEAD.encode("ascii"))
            for ref, ids in object_ids.items():
                _check_stop(stop)
                mesh = _mesh_xml(parts[ref]['stl_path'], parts[ref]['name'])
                for object_id in ids:
                    _check_stop(stop)
                    model.write(f'<object id="{object_id}" name={quoteattr(names[object_id - 1])} type="model">'
                                .encode("ascii"))
                    model.write(mesh)
                    model.write(b"</object>\n")
                del mesh                  # freed before the next part's mesh text is built
            model.write(b"</resources>\n<build>\n")
            for object_id, instance in enumerate(instances, start=1):
                footprint = parts[instance['ref']]['footprints'][instance['orientation']]
                model.write(f'<item objectid="{object_id}" transform={quoteattr(_transform(instance, footprint))}/>\n'
                            .encode("ascii"))
            model.write(b"</build>\n</model>\n")
    return names


def delivered_file_name(part_names, local_time, now=None):
    """`<first part>[_plus<N>]-<YYYYMMDD-HHMM>.gcode.3mf`; `part_names` are the distinct
    parts in instance order. The caller's local time when it matches LOCAL_TIME_RE, else UTC."""
    name = sanitize_part_name(part_names[0])
    if len(part_names) > 1:
        name += f"_plus{len(part_names) - 1}"
    if not (isinstance(local_time, str) and LOCAL_TIME_RE.fullmatch(local_time)):
        local_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y%m%d-%H%M")
    return f"{name}-{local_time}{ARCHIVE_SUFFIX}"


def check_plate_names(expected, found):
    """Raise SliceError(LEFT_OFF_MESSAGE) unless Orca sliced exactly the expected objects
    (found: slicer.plate_object_names). `where` names the first missing instance.

    Orca leaves a part that is entirely off the plate out of the slice without an error;
    this is what notices."""
    if sorted(found) == sorted(expected) and all(name.strip() for name in found):
        return
    missing = sorted(set(expected) - set(found))
    extra = sorted(set(found) - set(expected))
    raise SliceError(LEFT_OFF_MESSAGE, f"expected {len(expected)} objects, found {len(found)}; "
                                       f"missing {missing}; unexpected {extra}",
                     error_code="slice.left_off_plate", where={"instance": missing[0]} if missing else None)
