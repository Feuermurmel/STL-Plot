import setuptools


setuptools.setup(
	name = 'stl-plot',
	version = '0.1',
	packages = ['stl_plot'],
	install_requires = ['numpy-stl'],
	entry_points = dict(
		console_scripts = [
			'stl-plot=stl_plot:script_main']))
