import argparse
import os

from stl_plot.plot import main


def parse_args():
	parser = argparse.ArgumentParser()

	parser.add_argument('input_file')
	parser.add_argument('-o', '--output-file')

	args = parser.parse_args()

	if args.output_file is None:
		basename, _ = os.path.splitext(args.input_file)

		args.output_file = basename + '.pdf'

	return args


main(**vars(parse_args()))
