import os, tempfile
from lib import util
import itertools, io, contextlib
from . import paths


_asymptote_command = os.environ.get('ASYMPTOTE', 'asy')


def set_asymptote_command(command):
	global _asymptote_command
	
	_asymptote_command = command


class CompileException(Exception):
	pass


def _asymptote(in_path, out_path, asymptote_dir, cwd):
	try:
		util.command(_asymptote_command, '-f', 'pdf', '-o', out_path, in_path,
			set_env = dict(ASYMPTOTE_DIR = asymptote_dir), cwd = cwd)
	except util.CommandError as e:
		raise Exception('Compiling {} failed: {}'.format(in_path, e)) from None


def compile(in_path: str, out_path: str = None, format = 'pdf'):
	assert format == 'pdf'
	
	if out_path is None:
		base_name, _ = os.path.splitext(in_path)
		
		out_path = base_name + '.' + format
	
	_, out_suffix = os.path.splitext(out_path)
	
	# Asymptote creates A LOT of temp files (presumably when invoking LaTeX) and leaves some of them behind. Thus we run asymptote in a temporary directory.
	with tempfile.TemporaryDirectory() as temp_dir:
		absolute_in_path = os.path.abspath(in_path)
		temp_out_path = os.path.join(temp_dir, 'out.pdf')
		
		_asymptote(absolute_in_path, 'out', os.path.dirname(absolute_in_path),
			temp_dir)
		
		if not os.path.exists(temp_out_path):
			raise util.UserError('Asymptote did not generate a PDF file.', in_path)
		
		# Write output files.
		util.rename_atomic(temp_out_path, out_path)


class File:
	"""
	Context manager which yields a File instance. The statements written to that instance are written to a file at the specified path.
	"""
	
	def __init__(self, file: io.TextIOBase):
		self.file = file
		self.variable_id_iter = itertools.count()
	
	def _write_line(self, line: str):
		print(line, file = self.file)
	
	def get_variable_name(self):
		return '_var_{}'.format(next(self.variable_id_iter))


class AsymptoteFile(File):
	def __init__(self, *args):
		super().__init__(*args)
		
		self._picture_stack_id_iter = itertools.count()
	
	def _serialize_path(self, path, closed):
		def iter_pairs():
			for x, y in path.vertices:
				yield self._serialize_value((x, y), False)
			
			if closed:
				yield 'cycle'
		
		variable = self.get_variable_name()
		
		self.write('path {};', variable)
		
		for i in _group(iter_pairs(), 500):
			self.write('{} = {} -- {};', variable, variable, ' -- '.join(i))
		
		return variable
	
	def _serialize_array(self, type, value, depth, close_paths):
		if depth:
			type += '[]' * depth
			variable = self.get_variable_name()
			
			self.write('{} {};', type, variable)
			
			for i in _group(value, 500):
				self.write('{}.append(new {} {{ {} }});', variable, type, ', '.join(
					self._serialize_array(type, j, depth - 1, close_paths) for j in
					i))
			
			return variable
		else:
			return self._serialize_value(value, close_paths)
	
	def _serialize_length(self, value):
		return '{}mm'.format(self._serialize_value(value, False))
	
	def _serialize_value(self, value, close_paths):
		if isinstance(value, paths.Path):
			return self._serialize_path(value, closed = close_paths)
		elif isinstance(value, paths.Polygon):
			return self._serialize_array('path', value.paths, 1, True)
		elif isinstance(value, tuple):
			return '({})'.format(', '.join(map(self._serialize_length, value)))
		else:
			# Let str.format() deal with it.
			return value
	
	def _format_expression(self, expression, *args):
		return expression.format(*[self._serialize_value(i, False) for i in args])
	
	def declare_array(self, type, elements, depth = 1):
		return self._serialize_array(type, elements, depth, False)
	
	@contextlib.contextmanager
	def transform(self, expression, *args):
		id = next(self._picture_stack_id_iter)
		saved_name = '_currentpicture_stack_{}'.format(id)
		transform_name = '_currentpicture_transform_{}'.format(id)
		
		self.write('transform {} = {};', transform_name,
			self._format_expression(expression, *args))
		self.write('picture {} = currentpicture;', saved_name)
		self.write('currentpicture = new picture;')
		
		yield
		
		self.write('add({}, {} * currentpicture);', saved_name, transform_name)
		self.write('currentpicture = {};', saved_name)
	
	def write(self, statement, *args):
		"""
		Write a statement to the file.
		
		The specified statement is formatted with the specified arguments using str.format(). The following types of arguments are handled specially:
		
		- paths.Path (forming an open path)
		- paths.Polygon (forming an array of closed paths)
		
		Other types are serialized using the default behavior of str.format().
		"""
		
		self._write_line(self._format_expression(statement, *args))


@contextlib.contextmanager
def open_write(path):
	with util.writing_text_file(path) as file:
		yield AsymptoteFile(file)


def _group(iterable, count):
	accu = []
	
	for i in iterable:
		if len(accu) >= count:
			yield accu
			
			accu = []
		
		accu.append(i)
	
	if accu:
		yield accu
