import math, numpy, argparse, os, tempfile
from fabricate import asymptote, polyhedra, linalg


def parse_args():
	parser = argparse.ArgumentParser()
	
	parser.add_argument('input_file')
	parser.add_argument('-o', '--output-file')
	
	args = parser.parse_args()
	
	if args.output_file is None:
		basename, _ = os.path.splitext(args.input_file)
		
		args.output_file = basename + '.pdf'
	
	return args


def main(input_file, output_file):
	polyhedron = polyhedra.Polyhedron.load_from_stl(input_file)
	
	projection = numpy.dot(linalg.rotation_matrix(.18, [1, 0, 0]), linalg.rotation_matrix(.125, [0, 0, 1]))
	
	def project(vector):
		return numpy.dot(projection, numpy.concatenate([vector, [0]]))[:3]
	
	def point(view):
		return tuple(project(view.vertex_coordinate)[:2])
	
	def normal_z(view):
		return project(polyhedra.face_normal(view))[2]
	
	with tempfile.TemporaryDirectory() as tempdir:
		asy_file = os.path.join(tempdir, 'out.asy')
		
		with asymptote.open_write(asy_file) as file:
			for view in polyhedron.edges:
				dihedral_angle = polyhedra.dihedral_angle(view, view.opposite)
				face_normal = normal_z(view)
				opposite_face_normal = normal_z(view.opposite)
				
				if (face_normal > 0) != (opposite_face_normal > 0):
					color = 'black + 0.1mm'
				elif math.pi - dihedral_angle > 0.3:
					color = 'blue + 0.05mm'
				else:
					color = None
				
				if color is not None:
					file.write('draw({} -- {}, {});', point(view), point(view.next), color)
		
		asymptote.compile(asy_file, output_file)


main(**vars(parse_args()))
