import abc
import contextlib
import io
import os
import re
import shutil
import subprocess
import sys


def log(message, *args):
	print(message.format(*args), file = sys.stderr)


class UserError(Exception):
	def __init__(self, message, *args):
		super(UserError, self).__init__(message.format(*args))


class Hashable(metaclass=abc.ABCMeta):
	def __eq__(self, other):
		return type(self) is type(other) \
		       and self._hashable_key() == other._hashable_key()

	def __hash__(self):
		return hash(self._hashable_key())

	@abc.abstractmethod
	def _hashable_key(self): pass


# def main(fn):
# 	"""Decorator for "main" functions. Decorates a function that should be called when the containing module is run as a script (e.g. via python -m <module>)."""
# 	
# 	frame = inspect.currentframe().f_back
# 	
# 	def wrapped_fn(*args, **kwargs):
# 		try:
# 			fn(*args, **kwargs)
# 		except UserError as e:
# 			print('Error:', e, file = sys.stderr)
# 			sys.exit(1)
# 		except KeyboardInterrupt:
# 			sys.exit(2)
# 	
# 	if frame.f_globals['__name__'] == '__main__':
# 		wrapped_fn(*sys.argv[1:])
# 	
# 	# Allow the main function also to be called explicitly
# 	return wrapped_fn


def rename_atomic(source_path, target_path):
	"""
	Move the file at source_path to target_path.
	
	If both paths reside on the same device, os.rename() is used, otherwise the file is copied to a temporary name next to target_path and moved from there using os.rename().
	"""
	
	source_dir_stat = os.stat(os.path.dirname(os.path.join('.', source_path)))
	target_dir_stat = os.stat(os.path.dirname(os.path.join('.', target_path)))
	
	if source_dir_stat.st_dev == target_dir_stat.st_dev:
		os.rename(source_path, target_path)
	else:
		temp_path = target_path + '~'
		
		shutil.copyfile(source_path, temp_path)
		os.rename(temp_path, target_path)


class CommandError(Exception):
	pass


@contextlib.contextmanager
def command_context(*args, remove_env = [], set_env = { }, cwd = None,
		stdout = None, stderr = None):
	env = dict(os.environ)
	
	for i in remove_env:
		if i in env:
			del env[i]
	
	for k, v in set_env.items():
		env[k] = v
	
	try:
		process = subprocess.Popen(args, env = env, cwd = cwd, stdout = stdout,
			stderr = stderr)
	except OSError as e:
		raise CommandError('Error running {}: {}'.format(args[0], e))
	
	try:
		yield process
	finally:
		try:
			# May throw if the caller has already called wait() or kill() or similar on the process.
			process.kill()
		except OSError:
			# Ignore exceptions here so we don't mask the already-being-thrown exception.
			pass
	
	if process.returncode:
		raise CommandError('Command failed: {}'.format(' '.join(args)))


def command(*args, remove_env = [], set_env = { }, cwd = None, stdout = None,
		stderr = None):
	with command_context(*args, remove_env = remove_env, set_env = set_env,
			cwd = cwd, stdout = stdout, stderr = stderr) as process:
		return process.communicate()


def bash_escape_string(string):
	return "'{}'".format(re.sub("'", "'"'"'"'"'"'"'", string))


@contextlib.contextmanager
def _temp_file_path(path):
	temp_path = os.path.abspath(path + '~')
	dir_path = os.path.dirname(temp_path)
	
	if not os.path.exists(dir_path):
		os.makedirs(dir_path)
	
	yield temp_path
	
	os.rename(temp_path, path)


@contextlib.contextmanager
def reading_file(path):
	with open(path, 'rb') as file:
		yield file


@contextlib.contextmanager
def reading_text_file(path):
	with reading_file(path) as file:
		yield io.TextIOWrapper(file, encoding = 'utf-8')


def read_file(path):
	with reading_file(path) as file:
		return file.read()


def read_text_file(path):
	with reading_text_file(path) as file:
		return file.read()


@contextlib.contextmanager
def writing_file(path):
	with _temp_file_path(path) as temp_path, open(temp_path, 'wb') as file:
		yield file
		
		file.flush()
		os.fsync(file.fileno())


@contextlib.contextmanager
def writing_text_file(path):
	with writing_file(path) as file:
		yield io.TextIOWrapper(file, encoding = 'utf-8', write_through = True)


def write_file(path, data: bytes):
	with writing_file(path) as file:
		file.write(data)


def write_text_file(path, data: str):
	with writing_text_file(path) as file:
		file.write(data)
