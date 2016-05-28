import math, abc, numpy
from . import linalg


class Path:
	"""
	Represents an open path which can be transformed and exported to Asymptote and OpenSCAD.
	
	You can join two paths like this:
	
	>>> p1 = path((0, 0), (1, 1))
	>>> p2 = path((2, 1))
	>>> p1 + p2
	"""
	
	def __init__(self, m: numpy.ndarray):
		s1, s2 = m.shape
		
		assert s1 == 3
		
		self.m = m
	
	def __add__(self, other):
		return join_paths(self, other)
	
	def __repr__(self):
		return 'Path({})'.format(self.m)
	
	def _transform(self, transformation):
		return type(self)(numpy.dot(transformation.m, self.m))
	
	@property
	def reversed(self):
		"""
		This path with the order of it's points reversed.
		"""
		
		return type(self)(numpy.fliplr(self.m))
	
	@property
	def vertices(self):
		"""
		Return the vertices of this path as a list of Vertex instances.
		"""
		
		return [(x, y) for x, y, _ in self.m.T]
	
	@property
	def finite(self):
		"""
		Returns whether none of the vertices in this path lie at infinite coordinates.
		"""
		
		return numpy.count_nonzero(self.m[2]) == self.m.shape[0]


_the_one = numpy.array([1], numpy.float64)
_the_zero = numpy.array([0], numpy.float64)


def _cast_vertex(v, direction = False):
	arr = numpy.array(v, numpy.float64)
	
	assert arr.shape == (2,)
	assert not direction or numpy.count_nonzero(arr)
	
	return numpy.concatenate((arr, _the_zero if direction else _the_one))


def path(*vertices):
	"""
	Return a path using the specified coordinates.
	
	The arguments can either be `Vertex` instances or 2-tuples containing the arguments for `vertex()`.

	Please not that a path without any vertices, when used in a polygon, is interpreted as the area of the whole plane. The reasoning behind this is that a (convex) polygon ca be interpreted as the intersection of the set of half-spaces created by converting each edge into a half-space. The intersection of zero half-planes is the full plane. (And it was a convenient hack solving the problem of representing the whole plane.)
	"""
	
	def iter_vertices():
		for v in vertices:
			yield _cast_vertex(v)
	
	return Path(numpy.array(list(iter_vertices())).reshape((-1, 3)).T)


def _cast_path(p):
	if not isinstance(p, Path):
		p = path(*p)
	
	return p


def join_paths(*paths):
	"""
	Join multiple paths into a single one.
	
	The arguments can either be `Path` instances or iterables of vertices. The vertices can be anything accepted by `path()`.
	"""
	
	return Path(numpy.concatenate([_cast_path(i).m for i in paths], 1))


# See http://www.angusj.com/delphi/clipper/documentation/Docs/Overview/Rounding.htm. We use half the available range because otherwise clipper may return coordinates outside the valid range of coordinates.
_clipper_range = (1 << 61)

# Chosen by fair dice roll.
_clipper_scale = 1 << 31

_quadrant_corners = [
	(_clipper_range, _clipper_range),
	(-_clipper_range, _clipper_range),
	(-_clipper_range, -_clipper_range),
	(_clipper_range, -_clipper_range)]


class Polygon:
	@property
	@abc.abstractmethod
	def paths(self):
		"""
		List of paths describing the boundaries of all disconnected parts of this polygon.
		
		Accessing this property on a composite polygon will lead to all intermediate operations and transformations being executed. The resulting polygon must be finite, otherwise an exception will be thrown.
		"""


class _ConcretePolygon(Polygon):
	def __init__(self, paths):
		assert isinstance(paths, list)
		
		for i in paths:
			_, n = i.m.shape
			
			if n < 3:
				raise ValueError(
					'Paths must have at least 3 vertices: {}'.format(i))
		
		self._paths = paths
	
	def _get_pyclipper_paths(self, tm: numpy.ndarray):
		def _iter_paths():
			for i in self._paths:
				def _iter_vertices():
					path = [self._scale_point(tm, j) for j in i.m.T]
					prev = path[-1]
					
					for j in path:
						if j != prev:
							prev = j
							
							yield j
				
				vertices = list(_iter_vertices())
				
				if len(vertices) > 2:
					yield vertices
		
		return list(_iter_paths())
	
	@property
	def paths(self):
		return self._paths


class _CompositePolygon(Polygon):
	def __init__(self):
		self._cached_paths = None
	
	@property
	def paths(self):
		if self._cached_paths is None:
			self._cached_paths = self._render()
		
		return self._cached_paths
	
	def _render(self):
		paths = self._get_pyclipper_paths(numpy.eye(3))
		
		def _iter_paths():
			for i in paths:
				def _iter_vertices():
					path = [(self._unscale(x), self._unscale(y)) for x, y in i]
					prev = path[-1]
					
					for j in path:
						if j != prev:
							prev = j
							
							yield j
				
				vertices = list(_iter_vertices())
				
				if len(vertices) > 2:
					yield path(*vertices)
		
		return list(_iter_paths())
	
	@classmethod
	def _unscale(cls, x):
		if not (-_clipper_range < x < _clipper_range):
			raise Exception('Result contains vertices at infinity.')
		
		return x / _clipper_scale


class _TransformedPolygon(_CompositePolygon):
	def __init__(self, polygon: Polygon, tm: numpy.ndarray):
		super().__init__()
		
		assert isinstance(tm, numpy.ndarray)
		
		self._polygon = polygon
		self._tm = tm
	
	def _get_pyclipper_paths(self, tm: numpy.ndarray):
		return self._polygon._get_pyclipper_paths(numpy.dot(tm, self._tm))


class _CombinedPolygon(_CompositePolygon):
	def __init__(self, left: Polygon, right: Polygon, operation):
		super().__init__()
		
		self._left = left
		self._right = right
		self._operation = operation
	
	def _get_pyclipper_paths(self, tm: numpy.ndarray):
		pc = pyclipper.Pyclipper()
		# pc.StrictlySimple = True
		
		for i in self._left._get_pyclipper_paths(tm):
			pc.AddPath(i, pyclipper.PT_SUBJECT, True)
		
		for i in self._right._get_pyclipper_paths(tm):
			pc.AddPath(i, pyclipper.PT_CLIP, True)
		
		solution = pc.Execute(self._operation, pyclipper.PFT_EVENODD,
			pyclipper.PFT_EVENODD)
		
		# Clipper can return paths that it itself considers invalid as input. ._.
		assert all(
			-_clipper_range <= k <= _clipper_range for i in solution for j in i for
			k in j), solution
		assert all(len(i) > 2 for i in solution)
		
		return solution


class _HalfPlane(_CompositePolygon):
	"""
	Special Polygon which represents a half-plane.
	"""
	
	def __init__(self, anchor: numpy.ndarray, direction: numpy.ndarray):
		super().__init__()
		
		self._anchor = anchor
		self._direction = direction
	
	def _get_pyclipper_paths(self, tm: numpy.ndarray):
		# Used to correct inversion of the direction for mirroring transformations. 
		det = numpy.linalg.det(tm[:2, :2])
		
		assert det
		
		# Anchor in the representation used for clipper.
		px, py = self._scale_point(tm, self._anchor)
		
		# Transformed direction as fractions.
		dx, dy = self._transform_coordinate(tm,
			self._direction / numpy.array([det, det, 1]))
		
		# Endpoints of the line segment inside the range supported by clipper.
		e1x, e1y = self._project_infinity(px, py, dx, dy)
		e2x, e2y = self._project_infinity(px, py, -dx, -dy)
		
		# Information about which clipper range edges the line segment's endpoints touch.
		r1 = self._get_clipper_range_edges(e1x, e1y)
		r2 = self._get_clipper_range_edges(e2x, e2y)
		
		def iter_points():
			i = 0
			
			yield e1x, e1y
			
			while not r1[i % 4]:
				i += 1
			
			while r1[i % 4]:
				i += 1
			
			i -= 1
			
			while not r2[i % 4]:
				yield _quadrant_corners[i % 4]
				i += 1
			
			yield e2x, e2y
		
		return [list(iter_points())]
	
	@classmethod
	def _project_infinity(cls, px, py, dx, dy):
		"""
		Project a point along a direction onto the border of the range supported by clipper.
		"""
		
		sx = -1 if dx < 0 else 1
		sy = -1 if dy < 0 else 1
		
		pqx = px * sx
		pqy = py * sy
		dqx = dx * sx
		dqy = dy * sy
		
		ex = cls._project_to_edge(pqy, pqx, dqy, dqx)
		ey = cls._project_to_edge(pqx, pqy, dqx, dqy)
		
		return ex * sx, ey * sy
	
	@classmethod
	def _project_to_edge(cls, p1, p2, d1, d2):
		if d1:
			return min(round(p2 + (_clipper_range - p1) * d2 / d1), _clipper_range)
		else:
			return _clipper_range
	
	@classmethod
	def _get_clipper_range_edges(cls, x, y):
		"""
		Calculate on which edges of the border of the range supported by clipper a point lies.
		"""
		
		return [
			x == _clipper_range,
			y == _clipper_range,
			-x == _clipper_range,
			-y == _clipper_range]


class _Plane(_CompositePolygon):
	"""
	Special Polygon which represents the whole plane.
	"""
	
	def _get_pyclipper_paths(self, tm: numpy.ndarray):
		return [_quadrant_corners]


def polygon(*paths):
	"""
	Create a polygon from a set of paths.
	
	Each of the specified paths is interpreted as being closed. If some of the polygons formed from paths overlap or a path self-intersects, a even-odd unwinding rule is applied to decide which parts belong to the area inside the final polygon.
	
	The arguments can either be `Path` instances or iterables of vertices. The vertices can be anything accepted by `path()`.
	"""
	
	return _ConcretePolygon([_cast_path(i) for i in paths])


def circle(n = 64):
	"""
	Return a polygon approximating a circle using a regular polygon with the specified number of sides.
	"""
	
	def iter_points():
		for i in range(n):
			t = i * util.tau / n
			
			yield math.cos(t), math.sin(t)
	
	return polygon(iter_points())


def square():
	"""
	Return a unit square with the lower left corner placed at the origin.
	"""
	
	return polygon([(0, 0), (1, 0), (1, 1), (0, 1)])


def strip(anchor, normal):
	"""
	Return an infinitely long strip. The 'anchor' point lies one edge and the 'normal' runs perpendicular to the strip, defining its width.
	"""
	anchor2 = tuple([ai + ni for ai, ni in zip(anchor, normal)])
	h1 = half_plane(anchor, linalg.rot_cw(normal))
	h2 = half_plane(anchor2, linalg.rot_ccw(normal))
	return h1 & h2


def half_plane(anchor, direction):
	"""
	Return a Polygon instance representing a half-plane delimited by a line. The delimiting line runs through the specified anchor and along the specified direction. The half-plane is to the left of the line when traveling along the line in the specified direction.
	"""
	
	return _HalfPlane(_cast_vertex(anchor), _cast_vertex(direction, True))


def plane():
	"""
	The everything.
	"""
	
	return _Plane()
