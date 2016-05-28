import fractions, math, numpy, argparse, os, tempfile, sys
from functools import reduce

from fabricate import asymptote, polyhedra, linalg, geometry
from lib import util


def parse_args():
	parser = argparse.ArgumentParser()
	
	parser.add_argument('input_file')
	parser.add_argument('-o', '--output-file')
	
	args = parser.parse_args()
	
	if args.output_file is None:
		basename, _ = os.path.splitext(args.input_file)
		
		args.output_file = basename + '.pdf'
	
	return args


def iter_progress(seq):
	for i, x in enumerate(seq):
		print(
			'  {}/{}\x1b[K\x1b[G'.format(i, len(seq)),
			end='',
			file=sys.stderr,
			flush=True)

		yield x


class Point(geometry.Point):
	def __init__(self, *, z, **kwargs):
		super().__init__(**kwargs)

		self.z = z


class Segment(geometry.Segment):
	def __init__(self, *, is_boundary, is_edge, **kwargs):
		super().__init__(**kwargs)

		self.is_boundary = is_boundary
		"""Whether the segment is part of the boundary between front and back faces."""

		self.is_edge = is_edge
		"""Whether the segment represents a visible internal edge between two front faces."""


def main(input_file, output_file):
	projection = reduce(
		numpy.dot,
		[
			linalg.rotation_matrix(.05, [1, 0, 0]),
			linalg.rotation_matrix(.05, [0, 1, 0]),
			linalg.rotation_matrix(-.25, [1, 0, 0])])
	min_angle = 0.3
	
	polyhedron = polyhedra.Polyhedron.load_from_stl(input_file)

	def project(vector):
		return numpy.dot(projection, numpy.concatenate([vector, [0]]))[:3]

	def normal_z(view):
		return project(polyhedra.face_normal(view))[2]

	def make_point(vertex_view : polyhedra.PolyhedronView):
		x, y, z = map(fractions.Fraction, project(vertex_view.vertex_coordinate))

		return Point(x = x, y = y, z = z)
	
	def make_segment(edge_view : polyhedra.PolyhedronView):
		dihedral_angle = polyhedra.dihedral_angle(edge_view, edge_view.opposite)
		left_face_visible = normal_z(edge_view) > 0
		right_face_visible = normal_z(edge_view.opposite) > 0

		# We need to orient this so that the edge is closed (i.e. no points are missing because two segment ending at the same point).
		if left_face_visible:
			oriented_edge_view = edge_view
		else:
			oriented_edge_view = edge_view.opposite

		return Segment(
			start = make_point(oriented_edge_view),
			end = make_point(oriented_edge_view.opposite),
			is_boundary = left_face_visible != right_face_visible,
			is_edge = left_face_visible
					  and right_face_visible
					  and math.pi - dihedral_angle > min_angle)
	
	def make_simplex(face_view : polyhedra.PolyhedronView):
		assert len(face_view.face_cycle) == 3
		
		return geometry.Simplex(
			p1 = make_point(face_view),
			p2 = make_point(face_view.next),
			p3 = make_point(face_view.next.next))
	
	drawn_segments = []
	border_segments = []
	
	util.log('Detecting edges ...')
	
	for i in polyhedron.edges:
		segment = make_segment(i)
		
		if segment.is_edge or segment.is_boundary:
			drawn_segments.append(segment)
		
		if segment.is_boundary:
			border_segments.append(segment)

	simplexes = [make_simplex(i) for i in polyhedron.faces]

	def iter_border_intersections(segment: Segment):
		yield fractions.Fraction(0)
		yield fractions.Fraction(1)

		for i in geometry.get_intersections(border_segments, [segment]):
			border_z = linalg.interpolate(i.segment_1.start.z, i.segment_1.end.z, i.t1)
			drawn_z = linalg.interpolate(i.segment_2.start.z, i.segment_2.end.z, i.t2)

			if drawn_z <= border_z:
				yield i.t2

	def has_face_intersections(point: Point):
		for i in geometry.get_simplex_intersections(simplexes, [point]):
			simplex_p1_z = i.simplex.p1.z
			simplex_p2_z = i.simplex.p2.z
			simplex_p3_z = i.simplex.p3.z
			simplex_z = simplex_p1_z + (simplex_p2_z - simplex_p1_z) * i.t1 + (simplex_p3_z - simplex_p1_z) * i.t2

			if i.point.z < simplex_z:
				return True
		else:
			return False

	def point_on_segment(segment: Segment, t):
		return Point(
			x = linalg.interpolate(segment.start.x, segment.end.x, t),
			y = linalg.interpolate(segment.start.y, segment.end.y, t),
			z = linalg.interpolate(segment.start.z, segment.end.z, t))

	util.log('Detecting boundary intersections ...')
	util.log(
		'border: {}, draw: {}, simplexes: {}',
		len(border_segments),
		len(drawn_segments),
		len(simplexes))

	with tempfile.TemporaryDirectory() as tempdir:
		asy_file = os.path.join(tempdir, 'out.asy')

		with asymptote.open_write(asy_file) as file:
			def draw(segment: Segment, a, b, pen):
				start = point_on_segment(segment, a)
				end = point_on_segment(segment, b)

				start = start.x, start.y
				end = end.x, end.y

				file.write('draw({} -- {}, {});', start, end, pen)

			for i in iter_progress(drawn_segments):
				positions = sorted(set(iter_border_intersections(i)))

				for a, b in zip(positions[:-1], positions[1:]):
					if not has_face_intersections(point_on_segment(i, (a + b) / 2)):
						if i.is_edge:
							style = 'blue + 0.05mm'
						else:
							style = 'black + 0.05mm'
					else:
						style = 'red + 0.02mm'

					draw(i, a, b, style)
		
		asymptote.compile(asy_file, output_file)


main(**vars(parse_args()))
