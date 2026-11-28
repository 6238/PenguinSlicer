"""The plate 3MF writer, the delivered name and the name guard (plate_3mf.py). No Orca run."""
import re
import weakref
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from shapely.geometry import MultiPoint, Polygon

from helpers import corrupt_entry, l_prism_stl, make_part, part_from_stl, write_names_archive
from penguin_slice import plate_3mf
from penguin_slice.mesh import MeshError, orientation_footprints, read_binary_stl, turned_footprint
from penguin_slice.plate import ORIENTATIONS, instance_hull, quaternion_matrix
from penguin_slice.plate_3mf import LEFT_OFF_MESSAGE, LOCAL_TIME_RE, check_plate_names, delivered_file_name, \
    write_plate_3mf
from penguin_slice.slicer import UNREADABLE_MESSAGE, SliceCancelled, SliceError, Stop, plate_object_names

NS = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
# The printer delivery's job suffix (`-j<7 or 8 hex>` before the extension), which a
# delivered name must never look like it already carries.
JOB_SUFFIX_RE = re.compile(r'-j[0-9a-fA-F]{7,8}(?=\.gcode\.3mf$)')


def read_model(path):
    with zipfile.ZipFile(path) as zf:
        entries = set(zf.namelist())
        root = ET.fromstring(zf.read('3D/3dmodel.model'))
    return entries, root


def placed_vertices(root):
    """(item, vertices placed by the item's transform) per build item."""
    objects = {o.get('id'): o for o in root.findall('m:resources/m:object', NS)}
    for item in root.findall('m:build/m:item', NS):
        matrix = np.array([float(v) for v in item.get('transform').split()]).reshape(4, 3)   # p' = [p 1] . M
        vertices = np.array([[float(v.get(k)) for k in 'xyz']
                             for v in objects[item.get('objectid')].findall('m:mesh/m:vertices/m:vertex', NS)])
        yield item, np.hstack([vertices, np.ones((len(vertices), 1))]) @ matrix


def instance(ref, x, y, orientation='+z', angle=0):
    return {'ref': ref, 'orientation': orientation, 'angle': angle, 'x': x, 'y': y}


@pytest.fixture
def stls(tmp_path):
    path = tmp_path / 'stls'
    path.mkdir()
    return path


class TestWriter:
    def test_one_object_per_instance_named_with_labels(self, tmp_path, stls):
        parts = {'a': make_part(stls, 'Bracket', (20, 10, 5)), 'b': make_part(stls, 'Spacer', (8, 8, 8))}
        instances = [instance('a', 50, 50), instance('a', 100, 50), instance('b', 150, 50)]
        names = write_plate_3mf(tmp_path / 'plate.3mf', instances, parts)
        assert names == ['Bracket #1', 'Bracket #2', 'Spacer #1']
        entries, root = read_model(tmp_path / 'plate.3mf')
        assert {'[Content_Types].xml', '_rels/.rels', '3D/3dmodel.model'} <= entries
        assert root.get('unit') == 'millimeter'
        objects = root.findall('m:resources/m:object', NS)
        assert [o.get('name') for o in objects] == names
        assert all(o.get('type') == 'model' for o in objects)
        assert len({o.get('id') for o in objects}) == 3
        items = root.findall('m:build/m:item', NS)
        assert [i.get('objectid') for i in items] == [o.get('id') for o in objects]
        # Each instance carries its part's de-duplicated mesh: a box is 8 vertices, 12 triangles.
        for obj in objects:
            assert len(obj.findall('m:mesh/m:vertices/m:vertex', NS)) == 8
            assert len(obj.findall('m:mesh/m:triangles/m:triangle', NS)) == 12

    def test_each_part_stl_is_read_once(self, tmp_path, stls):
        parts = {'a': make_part(stls, 'Bracket', (20, 10, 5))}
        write_plate_3mf(tmp_path / 'first.3mf', [instance('a', 50, 50)], parts)
        stl_bytes = parts['a']['stl_path'].read_bytes()
        reads = []
        real_read = type(parts['a']['stl_path']).read_bytes

        def counting_read(path_self):
            reads.append(path_self)
            return real_read(path_self)

        from unittest import mock
        with mock.patch.object(type(parts['a']['stl_path']), 'read_bytes', counting_read):
            write_plate_3mf(tmp_path / 'plate.3mf', [instance('a', 50, 50), instance('a', 100, 50), instance('a', 150, 50)],
                            parts)
        assert reads == [parts['a']['stl_path']]
        assert parts['a']['stl_path'].read_bytes() == stl_bytes

    def test_same_named_parts_get_distinct_object_names(self, tmp_path, stls):
        parts = {'a': make_part(stls, 'Bracket', (20, 10, 5)), 'b': make_part(stls, 'Bracket', (8, 8, 8)),
                 'c': make_part(stls, 'Brack?t', (8, 8, 8))}
        instances = [instance('a', 50, 50), instance('b', 100, 50), instance('a', 150, 50), instance('c', 200, 50)]
        assert write_plate_3mf(tmp_path / 'plate.3mf', instances, parts) == \
            ['Bracket #1', 'Bracket #2', 'Bracket #3', 'Brack_t #1']

    def test_transform_read_back_puts_footprint_centre_at_xy(self, tmp_path, stls):
        # Uncentred, so the footprint offset matters.
        parts = {'a': make_part(stls, 'Bracket', (40, 10, 6), origin=(5.0, -3.0, 2.0))}
        cases = [('+z', 0, 100.0, 120.0), ('+x', 30, 150.5, 80.25), ('-y', 275, 60.0, 200.0), ('-z', 90, 170.0, 160.0)]
        write_plate_3mf(tmp_path / 'plate.3mf', [instance('a', x, y, o, a) for o, a, x, y in cases], parts)
        _entries, root = read_model(tmp_path / 'plate.3mf')
        for (_item, placed), (_o, _a, x, y) in zip(placed_vertices(root), cases):
            low, high = placed.min(axis=0), placed.max(axis=0)
            assert (low[0] + high[0]) / 2 == pytest.approx(x, abs=1e-3)
            assert (low[1] + high[1]) / 2 == pytest.approx(y, abs=1e-3)
            assert low[2] == pytest.approx(0.0, abs=1e-3)

    def test_asymmetric_part_footprint_matches_placement_in_every_orientation(self, tmp_path, stls):
        # The 3MF must put the part where plate.py's check sees it: the hull of the
        # transformed vertices equals instance_hull, which pins the rotation direction.
        part = part_from_stl(stls, 'Ell', l_prism_stl(origin=(7.0, -4.0, 3.0)))
        instances = [instance('a', 60.0 + 40 * k, 90.0 + 15 * k, o, 37) for k, o in enumerate(ORIENTATIONS)]
        write_plate_3mf(tmp_path / 'plate.3mf', instances, {'a': part})
        _entries, root = read_model(tmp_path / 'plate.3mf')
        for (_item, placed), placed_instance in zip(placed_vertices(root), instances):
            written = MultiPoint(placed[:, :2].tolist()).convex_hull
            expected = Polygon(instance_hull(placed_instance, part['footprints'][placed_instance['orientation']]))
            assert expected.area > 100
            assert written.symmetric_difference(expected).area < 0.05, placed_instance['orientation']
            assert placed[:, 2].min() == pytest.approx(0.0, abs=1e-3)

    def test_a_rotation_is_written_where_the_placement_check_sees_it(self, tmp_path, stls):
        """An instance laid by a `rotation`: the hull of its written vertices is the footprint
        the check uses for that turn, after the angle (contracts/plate-configuration.md)."""
        part = part_from_stl(stls, 'Ell', l_prism_stl(origin=(7.0, -4.0, 3.0)))
        rotation = (0.707106781, -0.588348405, 0.39223227, 0.0)
        mesh = read_binary_stl(l_prism_stl(origin=(7.0, -4.0, 3.0)), 'Ell')
        part['footprints'][rotation] = turned_footprint(mesh, quaternion_matrix(rotation))
        placed_instance = {'ref': 'a', 'rotation': list(rotation), 'angle': 15, 'x': 120.0, 'y': 140.0}
        write_plate_3mf(tmp_path / 'plate.3mf', [placed_instance], {'a': part})
        _entries, root = read_model(tmp_path / 'plate.3mf')
        ((_item, placed),) = placed_vertices(root)
        written = MultiPoint(placed[:, :2].tolist()).convex_hull
        expected = Polygon(instance_hull(placed_instance, part['footprints'][rotation]))
        assert expected.area > 100
        assert written.symmetric_difference(expected).area < 0.05
        assert placed[:, 2].min() == pytest.approx(0.0, abs=1e-3)

    def test_a_part_in_inches_is_written_in_millimetres(self, tmp_path, stls):
        part = make_part(stls, 'Block', (1, 2, 0.5))
        mesh = read_binary_stl(part['stl_path'].read_bytes(), 'Block', scale=25.4)
        part.update(scale=25.4, footprints=orientation_footprints(mesh))
        write_plate_3mf(tmp_path / 'plate.3mf', [instance('a', 100.0, 80.0)], {'a': part})
        _entries, root = read_model(tmp_path / 'plate.3mf')
        ((_item, placed),) = placed_vertices(root)
        assert (placed.max(axis=0) - placed.min(axis=0)).tolist() == pytest.approx([25.4, 50.8, 12.7], abs=1e-3)
        assert ((placed.max(axis=0) + placed.min(axis=0)) / 2)[:2].tolist() == pytest.approx([100.0, 80.0], abs=1e-3)

    def test_names_xml_escaped_and_sanitized(self, tmp_path, stls):
        parts = {'a': make_part(stls, 'A&B "q" <x>', (10, 10, 10))}
        assert write_plate_3mf(tmp_path / 'plate.3mf', [instance('a', 50, 50)], parts) == ['A_B__q___x_ #1']
        _entries, root = read_model(tmp_path / 'plate.3mf')     # parses: the XML is well formed
        assert root.find('m:resources/m:object', NS).get('name') == 'A_B__q___x_ #1'

    def test_unreadable_stl_refused_while_writing(self, tmp_path, stls):
        parts = {'a': make_part(stls, 'Bracket', (20, 10, 5))}
        parts['a']['stl_path'].write_bytes(b'solid ascii\nendsolid ascii\n')
        with pytest.raises(MeshError) as caught:
            write_plate_3mf(tmp_path / 'plate.3mf', [instance('a', 50, 50)], parts)
        assert caught.value.message == 'The file for Bracket is not an STL file.'
        assert caught.value.details.startswith(f"{parts['a']['stl_path']}: ")

    def test_stl_gone_after_the_check_is_a_missing_part(self, tmp_path, stls):
        # The plate configuration passed its checks, then the STL went away before the plate was written.
        parts = {'a': make_part(stls, 'Bracket', (20, 10, 5))}
        parts['a']['stl_path'].unlink()
        with pytest.raises(SliceError) as caught:
            write_plate_3mf(tmp_path / 'plate.3mf', [instance('a', 50, 50)], parts)
        assert (caught.value.error_code, caught.value.message, caught.value.where) == (
            'slice.part_missing', 'The file for Bracket is missing.', {'part': 'Bracket'})
        assert 'No such file or directory' in caught.value.details


class CountingStop(Stop):
    """A Stop that counts how often the writer looks at it, and is set at the look `set_at`."""

    def __init__(self, set_at=None):
        super().__init__()
        self.looks, self.set_at = 0, set_at

    def is_set(self):
        self.looks += 1
        if self.looks == self.set_at:
            self.set("cancel")
        return super().is_set()


class TestStopDuringTheWrite:
    """A replacement, a shutdown or a requested cancel sets the slice job's stop; the write looks at it
    before every part's mesh and every object, so it ends within one object's write."""

    def test_a_stop_set_after_the_first_parts_mesh_ends_the_write(self, tmp_path, stls, monkeypatch):
        parts = {ref: make_part(stls, name, (10, 10, 5)) for ref, name in (('a', 'A'), ('b', 'B'), ('c', 'C'))}
        stop, built = Stop(), []
        real_mesh_xml = plate_3mf._mesh_xml

        def mesh_then_cancel(stl_path, name, scale):
            built.append(name)
            stop.set("cancel")
            return real_mesh_xml(stl_path, name, scale)

        monkeypatch.setattr(plate_3mf, '_mesh_xml', mesh_then_cancel)
        instances = [instance(ref, 30 + 30 * n, 50) for n, ref in enumerate('abcabc')]
        with pytest.raises(SliceCancelled) as caught:
            write_plate_3mf(tmp_path / 'plate.3mf', instances, parts, stop=stop)
        assert built == ['A']
        assert caught.value.error_code == 'slice.cancelled'
        assert caught.value.details == ('stopped by the slice service (cancel) while the plate was being written, '
                                        'before Orca was started')

    @pytest.mark.parametrize('set_at', [1, 2, 3, 4])
    def test_a_stop_set_between_two_objects_of_one_part_ends_the_write(self, tmp_path, stls, set_at):
        parts = {'a': make_part(stls, 'Spacer', (10, 10, 5))}
        stop = CountingStop(set_at)
        with pytest.raises(SliceCancelled):
            write_plate_3mf(tmp_path / 'plate.3mf', [instance('a', 20 + 20 * n, 50) for n in range(3)], parts,
                            stop=stop)
        assert stop.looks == set_at          # nothing more was written once it was set

    def test_the_writer_looks_at_the_stop_before_each_mesh_and_each_object(self, tmp_path, stls):
        parts = {'a': make_part(stls, 'Spacer', (10, 10, 5)), 'b': make_part(stls, 'Hub', (12, 12, 5))}
        stop = CountingStop()
        instances = [instance(ref, 20 + 20 * n, 50) for n, ref in enumerate('ababa')]
        write_plate_3mf(tmp_path / 'plate.3mf', instances, parts, stop=stop)
        assert stop.looks == len(parts) + len(instances)

    def test_one_parts_mesh_text_at_a_time_objects_grouped_by_part(self, tmp_path, stls):
        # The objects are written part by part, so only one part's mesh text is held at a
        # time; their ids and the build items keep the instances' order and names.
        parts = {'a': make_part(stls, 'Spacer', (10, 10, 5)), 'b': make_part(stls, 'Hub', (12, 12, 7))}
        instances = [instance(ref, 20 + 20 * n, 50) for n, ref in enumerate('abab')]
        names = write_plate_3mf(tmp_path / 'plate.3mf', instances, parts)
        assert names == ['Spacer #1', 'Hub #1', 'Spacer #2', 'Hub #2']
        _entries, root = read_model(tmp_path / 'plate.3mf')
        objects = root.findall('m:resources/m:object', NS)
        assert [o.get('name') for o in objects] == ['Spacer #1', 'Spacer #2', 'Hub #1', 'Hub #2']
        by_id = {o.get('id'): o for o in objects}
        items = root.findall('m:build/m:item', NS)
        assert [i.get('objectid') for i in items] == ['1', '2', '3', '4']
        assert [by_id[i.get('objectid')].get('name') for i in items] == names
        for (_item, placed), placed_instance in zip(placed_vertices(root), instances):
            low, high = placed.min(axis=0), placed.max(axis=0)
            assert (low[0] + high[0]) / 2 == pytest.approx(placed_instance['x'], abs=1e-3)
            assert high[2] - low[2] == pytest.approx(5 if placed_instance['ref'] == 'a' else 7, abs=1e-3)

    def test_each_parts_mesh_text_is_released_before_the_next_is_built(self, tmp_path, stls, monkeypatch):
        # The write's memory is one part's mesh text, not every part's: a weak reference to
        # each mesh text built (a memoryview, which takes one) is dead by the time the next
        # part's is built, and none outlives the write. A cache or a list of meshes fails here.
        parts = {ref: make_part(stls, name, (10 + n, 10, 5)) for n, (ref, name) in enumerate((('a', 'A'), ('b', 'B'),
                                                                                              ('c', 'C')))}
        real_mesh_xml, built, alive_at_each_build = plate_3mf._mesh_xml, [], []

        def tracked_mesh_xml(stl_path, name, scale):
            alive_at_each_build.append([ref() is not None for ref in built])
            text = memoryview(real_mesh_xml(stl_path, name, scale))
            built.append(weakref.ref(text))
            return text

        monkeypatch.setattr(plate_3mf, '_mesh_xml', tracked_mesh_xml)
        instances = [instance(ref, 20 + 20 * n, 50) for n, ref in enumerate('abcabc')]
        names = write_plate_3mf(tmp_path / 'plate.3mf', instances, parts)
        assert alive_at_each_build == [[], [False], [False, False]]
        assert [ref() for ref in built] == [None, None, None]
        _entries, root = read_model(tmp_path / 'plate.3mf')      # the memoryviews were written whole
        assert [o.get('name') for o in root.findall('m:resources/m:object', NS)] == \
            [names[n] for n in (0, 3, 1, 4, 2, 5)]
        assert all(len(o.findall('m:mesh/m:vertices/m:vertex', NS)) == 8
                   for o in root.findall('m:resources/m:object', NS))


class TestDeliveredName:
    NOW = datetime(2026, 10, 9, 21, 32, tzinfo=timezone.utc)

    def test_patterns(self):
        assert delivered_file_name(['Bracket', 'Spacer', 'Hub'], '20261009-1432') == \
            'Bracket_plus2-20261009-1432.gcode.3mf'
        assert delivered_file_name(['Bracket'], '20261009-1432') == 'Bracket-20261009-1432.gcode.3mf'
        assert delivered_file_name(['A&B'], '20261009-1432') == 'A_B-20261009-1432.gcode.3mf'

    @pytest.mark.parametrize('bad', ['2026-10-09', None, '20261009-1432\n', 'x' * 13, 20261009])
    def test_unusable_local_time_falls_back_to_utc(self, bad):
        assert delivered_file_name(['Bracket'], bad, now=self.NOW) == 'Bracket-20261009-2132.gcode.3mf'

    def test_fallback_converts_to_utc(self):
        pacific = timezone(timedelta(hours=-7))
        assert delivered_file_name(['Box'], None, now=datetime(2026, 10, 9, 14, 32, tzinfo=pacific)) == \
            'Box-20261009-2132.gcode.3mf'

    def test_fallback_without_now_uses_the_current_utc_minute(self):
        assert re.fullmatch(r'Bracket-\d{8}-\d{4}\.gcode\.3mf', delivered_file_name(['Bracket'], None))

    @pytest.mark.parametrize('parts', [['j1234567'], ['Box', 'j1234567'], ['x-j1234567'], ['j12345678']])
    def test_never_looks_like_a_delivery_job_suffix(self, parts):
        assert LOCAL_TIME_RE.match('20261009-1432')
        assert JOB_SUFFIX_RE.search(delivered_file_name(parts, '20261009-1432')) is None


class TestNameGuard:
    def test_matching_names_pass_in_any_order(self):
        check_plate_names(['Box #1', 'Box #2'], ['Box #2', 'Box #1'])

    @pytest.mark.parametrize('found', [['Box #1'], ['Box #1', ''], ['Box #1', 'Box #2', 'Box #3'], [],
                                       ['Box #1', 'Box #1']])
    def test_missing_blank_extra_or_repeated_names_fail(self, found):
        with pytest.raises(SliceError) as caught:
            check_plate_names(['Box #1', 'Box #2'], found)
        assert caught.value.message == LEFT_OFF_MESSAGE == "A part was left off the plate."
        assert caught.value.error_code == "slice.left_off_plate"
        assert caught.value.details.startswith(f"expected 2 objects, found {len(found)}; missing ")

    def test_where_names_the_first_missing_instance_or_nothing(self):
        with pytest.raises(SliceError) as caught:
            check_plate_names(['Box #1', 'Box #2', 'Box #3'], ['Box #2'])
        assert caught.value.where == {'instance': 'Box #1'}
        with pytest.raises(SliceError) as caught:
            check_plate_names(['Box #1'], ['Box #1', 'Box #9'])
        assert caught.value.where == {}

    def test_blank_names_fail_even_when_expected(self):
        with pytest.raises(SliceError):
            check_plate_names(['', 'Box #1'], ['', 'Box #1'])

    def test_details_name_the_missing_and_unexpected(self):
        with pytest.raises(SliceError) as caught:
            check_plate_names(['Box #1', 'Hub #1'], ['Box #1', 'Peg #1'])
        assert caught.value.details == "expected 2 objects, found 2; missing ['Hub #1']; unexpected ['Peg #1']"

    def test_object_names_read_from_archive(self, tmp_path):
        path = tmp_path / 'plate.gcode.3mf'
        write_names_archive(path, ['Box #1', 'Hub #1'])
        assert plate_object_names(path) == ['Box #1', 'Hub #1']

    def test_unnamed_object_reads_as_blank(self, tmp_path):
        path = tmp_path / 'plate.gcode.3mf'
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr('Metadata/plate_1.json', '{"bbox_objects": [{"name": null}, {}]}')
        assert plate_object_names(path) == ['', '']

    @pytest.mark.parametrize('content', [None, 'not json', '[1, 2]', '{"bbox_objects": null}', '{}',
                                         '{"bbox_objects": "Box #1"}', '{"bbox_objects": ["Box #1"]}',
                                         b'{"bbox_objects": [{"name": "Br\xe4cket"}]}'])
    def test_unreadable_plate_json(self, tmp_path, content):
        path = tmp_path / 'plate.gcode.3mf'
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr('Metadata/plate_1.gcode', '')
            if content is not None:
                zf.writestr('Metadata/plate_1.json', content)
        with pytest.raises(SliceError) as caught:
            plate_object_names(path)
        assert caught.value.message == UNREADABLE_MESSAGE
        assert caught.value.error_code == 'slice.unreadable_output'
        assert caught.value.details.startswith('Metadata/plate_1.json: ')

    def test_archive_that_is_not_a_zip(self, tmp_path):
        path = tmp_path / 'plate.gcode.3mf'
        path.write_bytes(b'nope')
        with pytest.raises(SliceError) as caught:
            plate_object_names(path)
        assert caught.value.message == UNREADABLE_MESSAGE

    def test_corrupt_entry_in_a_readable_zip(self, tmp_path):
        path = tmp_path / 'plate.gcode.3mf'
        corrupt_entry(path, 'Metadata/plate_1.json', b'{"bbox_objects": []}' * 200)
        with pytest.raises(SliceError) as caught:
            plate_object_names(path)
        assert caught.value.error_code == 'slice.unreadable_output'
        assert caught.value.details.startswith('Metadata/plate_1.json: ')
