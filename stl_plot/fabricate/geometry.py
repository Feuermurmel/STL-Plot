import fractions, typing

from stl_plot.util import Hashable


class Point(Hashable):
	def __init__(self, x : fractions.Fraction, y : fractions.Fraction):
		self.x = x
		self.y = y

	def __repr__(self):
		return 'Point({0.x}, {0.y})'.format(self)

	def _hashable_key(self):
		return self.x, self.y


class Segment(Hashable):
	def __init__(self, start : Point, end : Point):
		self.start = start
		self.end = end

	def _hashable_key(self):
		return self.start, self.end


class Intersection:
	def __init__(self, segment_1 : Segment, segment_2 : Segment, point : Point, t1 : fractions.Fraction, t2: fractions.Fraction):
		self.segment_1 = segment_1
		self.segment_2 = segment_2
		self.point = point
		self.t1 = t1
		self.t2 = t2
	
	@classmethod
	def for_segments(cls, segment_1 : Segment, segment_2 : Segment):
		"""
		Returns None for parallel segments.
		"""
		
		s1x = segment_1.start.x
		s1y = segment_1.start.y
		s2x = segment_2.start.x
		s2y = segment_2.start.y
		
		d1x = segment_1.end.x - s1x
		d1y = segment_1.end.y - s1y
		d2x = segment_2.end.x - s2x
		d2y = segment_2.end.y - s2y
		
		v = d1y * d2x - d1x * d2y
		
		if v != 0:
			t1 = (d2y * s1x - d2x * s1y - d2y * s2x + d2x * s2y) / v
			t2 = (d1y * s1x - d1x * s1y - d1y * s2x + d1x * s2y) / v
			
			if 0 <= t1 < 1 and 0 <= t2 < 1:
				x = s1x + d1x * t1
				y = s1y + d1y * t1
				
				return cls(segment_1, segment_2, Point(x, y), t1, t2)
		
		return None


def iter_intersections(lines: typing.List[Segment], line: Segment):
	for i in lines:
		intersection = Intersection.for_segments(i, line)

		if intersection is not None:
			yield intersection


class Simplex:
	def __init__(self, p1 : Point, p2 : Point, p3 : Point):
		self.p1 = p1
		self.p2 = p2
		self.p3 = p3

	def __repr__(self):
		return 'Simplex({0.p1}, {0.p2}, {0.p3})'.format(self)


class SimplexIntersection:
	def __init__(self, simplex: Simplex, point: Point, t1 : fractions.Fraction, t2: fractions.Fraction):
		self.simplex = simplex
		self.point = point
		self.t1 = t1
		self.t2 = t2
	
	@classmethod
	def for_simplex_and_point(cls, simplex: Simplex, point: Point):
		"""
		Returns None if the simplex has no area.
		"""
		x = point.x
		y = point.y
		x1 = simplex.p1.x
		y1 = simplex.p1.y
		
		d1x = simplex.p2.x - x1
		d1y = simplex.p2.y - y1
		d2x = simplex.p3.x - x1
		d2y = simplex.p3.y - y1

		n = d1y * d2x - d1x * d2y

		if n == 0:
			return None
		else:
			t1 = (d2y * x1 - d2y * x + d2x * y - d2x * y1) / n
			t2 = (d1y * x - d1y * x1 - d1x * y + d1x * y1) / n

			if 0 <= t1 and 0 <= t2 and t1 + t2 <= 1:
				return cls(simplex, point, t1, t2)
			else:
				return None


def iter_simplex_intersections(simplexes: typing.List[Simplex], point: Point):
	for i in simplexes:
		intersection = SimplexIntersection.for_simplex_and_point(i, point)

		if intersection is not None:
			yield intersection
