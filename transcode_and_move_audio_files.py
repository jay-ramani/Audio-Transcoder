# -------------------------------------------------------------------------------
# Name        : Transcode and Move Audio Files
# Purpose     : Transcode and move converted audio files to the drive specified.
#             : The same directory structure found for the source files will be
#             : recreated under the drive/directory specified as target.
# Author      : Jayendran Jayamkondam Ramani
# Created     : 3:20 PM + 5:30 IST 02 November 2018
# Copyright   : (c) Jayendran Jayamkondam Ramani
# Licence     : GPL v3
# Dependencies: Requires the following packages
#                   - win32api package (pip install pypiwin32)
#                   - win10toast (pip install win10toast; for toast notifications)
#                   - appdirs (pip install appdirs; to access application/log directions in a platform agnostic manner)
# -------------------------------------------------------------------------------

import argparse
import logging
import os
import pathlib
import platform
import shlex
import shutil
import subprocess
import sys
import time
import math

from shlex import quote
from contextlib import suppress


# Show tool tip/notification/toast message
def show_toast(tooltip_title, tooltip_message):
	# Handle tool tip notification (Linux)/balloon tip (Windows; only OS v10 supported for now)
	tooltip_message = os.path.basename(__file__) + ": " + tooltip_message

	if platform.system() == "Linux":
		os.system("notify-send \"" + tooltip_title + "\" \"" + tooltip_message + "\"")
	else:
		from win10toast import ToastNotifier

		toaster = ToastNotifier()
		toaster.show_toast(tooltip_title, tooltip_message, icon_path = None, duration = 5)


# Return the platform specific dictionary having command line transcode tools and
# their options
# Note: To the caller of this function:
# dict_transcode_tool[format][0] refers to the transoder
# dict_transcode_tool[format][1] refers to the transcoder's options.
#
# TODO: Implement more target formats like ogg in the future.
def dict_transcode_tool_platform_get(operation_transcode = "encode"):
	opus = "opus"
	flac = "flac"

	# Use a dictionary to map a file type (key) to its transcoding tool (value).
	# Assign a blank string to video file types yet unsupported.

	# Not all formats can be converted to the target by opustools. Hence, we have this
	# list for valid source formats for specific targets.
	valid_encode_source_for_opus = ("wav", "aiff", "flac", "oga", "pcm")
	valid_encode_target_for_opus_source = opus
	valid_decode_source_for_opus = opus
	valid_decode_target_for_opus = "wav"

	# Not all formats can be converted to the target by flac. Hence, we have this list
	# for valid source formats for specific targets.
	valid_encode_source_for_flac = ("wav", "aiff", "rf64", "w64")
	valid_encode_target_for_flac_source = flac
	valid_decode_source_for_flac = flac
	valid_decode_target_for_flac = "wav"

	if operation_transcode == "encode":
		dict_valid_source = {
			opus: valid_encode_source_for_opus,
			flac: valid_encode_source_for_flac
		}
		dict_valid_target = {
			opus: valid_encode_target_for_opus_source,
			flac: valid_encode_target_for_flac_source
		}
	else:
		dict_valid_source = {
			opus: valid_decode_source_for_opus,
			flac: valid_decode_source_for_flac
		}
		dict_valid_target = {
			opus: valid_decode_target_for_opus,
			flac: valid_decode_target_for_flac
		}

	# Command line options for transcoding tools

	# Options for the Opus encoder
	# Used with the ffmpeg binary
	# options_opus = ("-v", "error", "-codec:a", "libopus", "-b:a", "160k", "-vbr", "on", "-frame_duration", "20", "-compression_level", "10", "-application", "audio", "-i")
	# Used with the opusenc binary
	options_encode_opus = ("--music", "--bitrate", "160", "--vbr", "--framesize", "20", "--comp", "10")
	# Options for the Opus decoder; none provided by opusdec except --quiet, which we don't want to use
	options_decode_opus = ()

	# Options for the flac binary
	# options_flac = ("--keep-foreign-metadata", "--replay-gain", "--mid-side", "--best", "--verify", "--")
	options_encode_flac = (
		"--keep-foreign-metadata", "--replay-gain", "--mid-side", "--best", "--verify", "--output-name")
	# --keep-foreign-metadata refuses to decode if there's no foreign metadata, so removing the option
	options_decode_flac = ("--decode", "--output-name")

	# Point to encoding binaries on Windows for supported formats
	dict_encode_tool_windows = {
		"opus": ("opusenc.exe", options_encode_opus),
		#		"opus": ("C:\\ffmpeg\\bin\\ffmpeg.exe", options_opus)
		"flac": ("flac.exe", options_encode_flac)
	}
	dict_decode_tool_windows = {
		"opus": ("opusdec.exe", options_decode_opus),
		#		"opus": ("C:\\ffmpeg\\bin\\ffmpeg.exe", options_opus)
		"flac": ("flac.exe", options_decode_flac)
	}

	# Point to decoding binaries on Linux for supported formats
	dict_encode_tool_linux = {
		"opus": ("/usr/bin/opusenc", options_encode_opus),
		#		"opus" : ("ffmpeg", options_opus)
		"flac": ("/usr/bin/flac", options_encode_flac)
	}
	dict_decode_tool_linux = {
		"opus": ("/usr/bin/opusdec", options_decode_opus),
		#		"opus" : ("ffmpeg", options_opus)
		"flac": ("/usr/bin/flac", options_decode_flac)
	}

	if platform.system() == "Windows":
		if operation_transcode == "encode":
			dict_transcode_tool = dict_encode_tool_windows
		else:
			dict_transcode_tool = dict_decode_tool_windows
	else:
		if operation_transcode == "encode":
			dict_transcode_tool = dict_encode_tool_linux
		else:
			dict_transcode_tool = dict_decode_tool_linux

	return dict_transcode_tool, dict_valid_source, dict_valid_target


# Return a tuple of main and relevant audio files
def main_and_relevant_files_for_audio_get(extension_target):
	return (extension_target, "mpc", "jpg", "jpeg", "png", "pls", "rtf", "txt", "accurip")


# Splits the path received into two parts:
# 1. the path received without the file's extension
# 2. the extension alone, lower case converted
def split_root_extension(source_path):
	root, extension = os.path.splitext(source_path)

	# Grab the part after the extension separator, and convert to lower case.
	# This is to ensure we don't skip files with extensions that Windows sets
	# to upper case. This is often the case with files downloaded from servers
	# or torrents.
	extension = (extension.rpartition(os.extsep)[2]).lower()

	return root, extension


# We support only Windows and Unix like OSes
def is_supported_platform():
	return platform.system() == "Windows" or platform.system() == "Linux"


# Open a file and log what we do
def logging_init():
	from appdirs import AppDirs

	# Use realpath instead to get through symlinks
	name_script_executable = os.path.basename(os.path.realpath(__file__)).partition(".")[0]
	dirs = AppDirs(name_script_executable, "Jay Ramani")

	try:
		os.makedirs(dirs.user_log_dir, exist_ok = True)
	except PermissionError:
		print("\aNo permission to write log files at \'" + dirs.user_log_dir + "\'!")
	except:
		print("\aUndefined exception!")
		print("Error", sys.exc_info())
	else:
		print("Check logging results at \'" + dirs.user_log_dir + "\'\n")

		# All good. Proceed with logging.
		logging.basicConfig(filename = dirs.user_log_dir + os.path.sep + name_script_executable + " - " +
		                               time.strftime("%Y%m%d%I%M%S%z") + '.log', level = logging.INFO,
		                    format = "%(message)s")
		logging.info("Log beginning at " + time.strftime("%d %b %Y (%a) %I:%M:%S %p %Z (GMT%z)") + " with PID: " + str(
			os.getpid()) + ", started with arguments " + str(sys.argv) + "\n")


# Formats the size, based on the value
def sizeof_fmt(num, suffix = 'B'):
	for unit in ('', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi'):
		if abs(num) < 1024.0:
			return "%3.1f%s%s" % (num, unit, suffix)
		num /= 1024.0

	return "%.1f%s%s" % (num, 'Yi', suffix)


# Print a spacer after every file's processing for sifting through the output
# and log
def print_and_log_spacer(count, file, size_file, operation):
	print("[File " + "{:>4}]".format(count) + "[{:>8}]".format(
		size_file) + " \'" + file + "\' " + operation + " complete\n")
	logging.info("[File " + "{:>4}]".format(count) + "[{:>8}]".format(
		size_file) + " \'" + file + "\' " + operation + " complete\n")


def move_or_copy_file(file_source, target_absolute_directory, extension_target):
	_, dict_valid_source, _ = dict_transcode_tool_platform_get()

	_, extension = split_root_extension(file_source)

	size_file = os.path.getsize(file_source)
	size_file_formatted = sizeof_fmt(size_file)

	# If it's a transcoded audio file, "move" it to the target.
	# Add to the dictionary keys if other formats are required.
	if extension in tuple(dict_valid_source.keys()):
		print("Moving \'" + file_source + "\' (" + size_file_formatted + ")\n-> \'" + target_absolute_directory + "\'")
		logging.info(
			"Moving \'" + file_source + "\' (" + size_file_formatted + ")\n-> \'" + target_absolute_directory + "\'")

		try:
			shutil.move(file_source, target_absolute_directory)
		except (OSError, IOError, shutil.Error) as error_move:
			print("Error moving file \'" + file_source + "\'\n-> \'" + target_absolute_directory + "\'")
			print(error_move.stderr)

			logging.error(
				"Error moving file \'" + file_source + "\'\n-> \'" + target_absolute_directory + "\' ")
			logging.error(error_move.stderr)
		else:
			# Specifically, keep count of the number of files moved
			move_or_copy_file.total_count_moved += 1
			# Keep count of the number of files processed
			move_or_copy_file.total_count += 1
			# Add up the statistic to later display how much data was moved
			move_or_copy_file.total_size += size_file

			print_and_log_spacer(move_or_copy_file.total_count, file_source, size_file_formatted, "move")
	# For album art and other non-transcoded audio (with exceptions like .mpc files,
	# "copy" to the target so we don't disturb the source's integrity
	elif extension in (main_and_relevant_files_for_audio_get(extension_target)[1:]):
		print("Copying \'" + file_source + "\' (" + size_file_formatted + ")\n-> \'" + target_absolute_directory + "\'")
		logging.info(
			"Copying \'" + file_source + "\' (" + size_file_formatted + ")\n-> \'" + target_absolute_directory + "\'")

		try:
			shutil.copy2(file_source, target_absolute_directory, follow_symlinks = True)
		except (OSError, IOError, shutil.Error) as error_copy:
			print("Error copying file \'" + file_source + "\' to \'" + target_absolute_directory + "\'")
			print(error_copy.stderr)

			logging.error(
				"Error copying file \'" + file_source + "\' to \'" + target_absolute_directory + "\' ")
			logging.error(error_copy.stderr)
		else:
			# Add up the statistic to later display how much data was moved
			move_or_copy_file.total_size += size_file
			# Keep count of the number of files processed
			move_or_copy_file.total_count += 1
			print_and_log_spacer(move_or_copy_file.total_count, file_source, size_file_formatted, "copy")


move_or_copy_file.total_count = 0
move_or_copy_file.total_count_moved = 0
move_or_copy_file.total_size = 0


def create_directory(target_absolute_directory):
	# Default directory creation result to success
	status = True

	# Attempt to create only if the target doesn't already exist
	if not os.path.exists(target_absolute_directory):
		try:
			pathlib.Path(target_absolute_directory).mkdir(parents = True, exist_ok = True)
		except (OSError, IOError, shutil.Error) as error_mkdir:
			# Screwed! Should mostly be a permission issue. Flag, and report error.
			status = False

			print("Error creating target directory path \'" + target_absolute_directory + "\'\n")
			print(error_mkdir.output)
			print(error_mkdir.stderr)

			logging.error(
				"Error creating target directory path \'" + target_absolute_directory + "\'\n")
			logging.error(error_mkdir.output)
			logging.error(error_mkdir.stderr)
		else:
			print("\nCreated directory \'" + target_absolute_directory + "\'\n")
			logging.info("\nCreated directory \'" + target_absolute_directory + "\'\n")

	return status


def build_target_and_operate(root_source, dir_source, file_source, dir_destination, extension_target):
	root, extension_source = split_root_extension(file_source)

	# Only process audio (actual audio, playlist, cue etc.) and image (album art) files.
	#
	# Note: We are only "moving" transcoded *audio* files (specified in the filter
	# list below), and will be "copying" any other relevant, but *non-audio* files
	# to not disturb the integrity of the source directory.
	if extension_source in main_and_relevant_files_for_audio_get(extension_target):
		# Stamp the start time in nanoseconds
		time_start = time.monotonic_ns()

		# Note: If we landed here walking the tree, file_source would only
		# contain the file's name without path. dir_source would contain the
		# path (relative, or absolute, based on what was passed on the command
		# line) of the file in question. Else, if we came here on getting a
		# straight file on the command line, dir_source would be an empty string,
		# still leading to a valid value in the statement below.
		path_file_source = os.path.join(dir_source, file_source)

		# We're dealing with walking through files in a directory passed by the caller
		if root_source and dir_source:
			# Append the back slash to the delimiter, else, partitioning adds a leading
			# backslash and os.path.join() screws the target!
			path_dir_relative_target = dir_source.partition(root_source + os.sep)[2]

			target_absolute_directory = os.path.join(dir_destination, path_dir_relative_target)

			create_directory(target_absolute_directory)

			# By now the target directory should be in place
			move_or_copy_file(path_file_source, target_absolute_directory, extension_target)
		else:
			# We're dealing *only* with a single file passed by the caller
			move_or_copy_file(os.path.join(dir_source, file_source), dir_destination, extension_target)

		# Stamp the end time in nanoseconds
		time_end = time.monotonic_ns()

		# Aggregate the numbers to provide a statistic at exit
		build_target_and_operate.total_time_ns_relocate += time_end - time_start


build_target_and_operate.total_time_ns_relocate = 0


# Transcode the source audio file to the intended target format
def transcode_source_audio(path_source_audio_file, format_target, operation_transcode, percentage_gather = False,
                           dict_files_failed = False):
	root, extension_original = split_root_extension(path_source_audio_file)

	# Save a reference for the (yet to be built) target file's extension to reflect
	# the target format
	extension = format_target.lower()

	INDEX_DICT_TRANSCODE_TOOL = 0
	# INDEX_DICT_TRANSCODE_TOOL_OPTIONS = 1

	# As an optimization for transcoding more than one file, if the current target
	# format is the same as the previous one, re-use validation that was already
	# done to save dictionary lookups and path checks
	if extension_original == transcode_source_audio.extension_prev:
		target = transcode_source_audio.target_prev
		is_valid_source = transcode_source_audio.is_valid_source_prev
		does_transcode_tool_exist = transcode_source_audio.does_transcode_tool_exist_prev
		transcode_tool = transcode_source_audio.transcode_tool_prev
		options = transcode_source_audio.options_prev
	else:
		# Save the current parameters for the next run. If we encounter the same target
		# in the next run, it saves dictionary lookups and checks.
		dict_transcode_tool, dict_valid_source, dict_valid_target = dict_transcode_tool_platform_get(
			operation_transcode)
		transcode_source_audio.extension_prev = extension_original
		transcode_source_audio.dict_transcode_tool_prev = dict_transcode_tool
		transcode_source_audio.dict_valid_source_prev = dict_valid_source
		transcode_source_audio.dict_valid_target_prev = dict_valid_target
		transcode_source_audio.target_prev = target = dict_valid_target[extension]
		transcode_source_audio.is_valid_source_prev = is_valid_source = extension_original.lower() in dict_valid_source[
			extension]
		transcode_source_audio.does_transcode_tool_exist_prev = does_transcode_tool_exist = os.path.isfile(
			dict_transcode_tool[extension][INDEX_DICT_TRANSCODE_TOOL])
		transcode_source_audio.transcode_tool_prev = transcode_tool = dict_transcode_tool[extension][
			INDEX_DICT_TRANSCODE_TOOL]
		transcode_source_audio.options_prev = options = (dict_transcode_tool[extension][1:])[0]

	# Save a reference for the (yet to be transcoded) target file
	path_target_audio_file = root + os.extsep + target

	# If ffmpeg is set as the Opus encoding tool, disable the check below as it
	# supports every possible format in the world!

	# Check if the source file format is valid for the transcoder
	if is_valid_source:
		# Proceed to transcode only if the target file does not already exist
		if not os.path.exists(path_target_audio_file):
			if percentage_gather:
				transcode_source_audio.total_count_source += 1

				# We're here only to get the total count of files to be transcoded, to report
				# the percentage of completion after every file. So return without any actual
				# processing.
				return

			# Check if the transcoding tool exists in the path defined
			if does_transcode_tool_exist:
				print("\nTranscoding \'" + path_source_audio_file + "\' to \'" + target.capitalize() + "\' format...\n")
				logging.info(
					"\nTranscoding \'" + path_source_audio_file + "\' to \'" + target.capitalize() + "\' format...\n")
				output_transcode = ""
				# Note: dict_transcode_tool[format_target][0] refers to the transcode tool path (absolute/relative)
				#       dict_transcode_tool[format_target][1] refers to the transcode tool's options
				#
				# WARNING: The order of arguments to the command line below are very important. Do not change
				# unless you know what you're tinkering with, or it will break the execution, and the obvious batch
				# processing which this function was invoked from.

				# Track transcoding start time in nano-seconds
				time_ns_start = time.monotonic_ns()

				try:
					# Make a whole tuple out of individual tuples and strings by concatenating
					output_transcode = subprocess.run(
						(transcode_tool, path_source_audio_file) + options + tuple([path_target_audio_file]),
						stdout = subprocess.PIPE, check = True, universal_newlines = True).stdout
				except subprocess.CalledProcessError as error_transcode:
					print(error_transcode.stderr)
					print(error_transcode.output)

					logging.error(error_transcode.stderr)
					logging.error(error_transcode.output)

					print("\aError transcoding \'" + path_source_audio_file + "\'")
					print("\aError", sys.exc_info())
					logging.error("Error transcoding \'" + path_source_audio_file + "\'" + str(sys.exc_info()))

					print("\nCommand that resulted in the exception: " + str(error_transcode.cmd) + "\n")
					logging.info("\nCommand that resulted in the exception: " + str(error_transcode.cmd) + "\n")

					# Append the failed transcoding to a dict with the reason. This will be used in printing
					# a statistic at exit.
					dict_files_failed[path_source_audio_file] = "\nIf the source is in wav format, transcode to " \
					                                            "flac. Else, if the source is in flac, transcode " \
					                                            "to wav, and then back to flac. This is most " \
					                                            "likely an error due to an incompatible PCM " \
					                                            "format, or due to the OS character set encoding."

					show_toast("Error", "Failed to convert one or more files. Check the log.")
				else:
					# Track transcoding end time in nano-seconds
					time_ns_end = time.monotonic_ns()

					# Keep track of the number of files transcoded to present a total statistic at exit
					transcode_source_audio.total_count_transcode += 1

					# Save the total time taken to transcode files thrown at us, to report a statistic at exit
					transcode_source_audio.total_time_ns_transcode += time_ns_end - time_ns_start
			else:
				print("No such transcode tool as \'" + transcode_tool + "\'. Is its path correct?")
				logging.error("No such transcode tool as \'" + transcode_tool + "\'. Is its path correct?")
		else:
			# No need to report if we're only gathering headcount. Hence, bolt out.
			if percentage_gather:
				return

			print(
				"Skipping \'" + path_source_audio_file + "\' as transcoded file \'" + path_target_audio_file + "\' already exists")
			logging.error(
				"Skipping \'" + path_source_audio_file + "\' as transcoded file \'" + path_target_audio_file + "\' already exists")

		# transcode_source_audio.total_count_source would not be greater than zero if a single file is being
		# dealt with, or percentage completion is not to be reported
		if transcode_source_audio.total_count_source and transcode_source_audio.total_count_transcode:
			percent_complete = str(
				math.floor(
					(transcode_source_audio.total_count_transcode / transcode_source_audio.total_count_source) * 100))

			if transcode_source_audio.total_count_transcode < transcode_source_audio.total_count_source:
				print("\n" + percent_complete + "% of files in queue transcoded\n")
				logging.info("\n" + percent_complete + "% of files in queue transcoded\n")
			else:
				print("All files in queue transcoded\n")
				logging.info("All files in queue transcoded\n")

	return path_target_audio_file


transcode_source_audio.total_time_ns_transcode = 0
transcode_source_audio.total_count_transcode = 0
transcode_source_audio.total_count_source = 0
transcode_source_audio.dict_transcode_tool_prev = None
transcode_source_audio.dict_valid_source_prev = None
transcode_source_audio.dict_valid_target_prev = None
transcode_source_audio.extension_prev = None
transcode_source_audio.is_valid_source_prev = None
transcode_source_audio.does_transcode_tool_exist_prev = None
transcode_source_audio.options_prev = None
transcode_source_audio.transcode_tool_prev = None
transcode_source_audio.target_prev = None


# Convert the time in nanoseconds passed to hours, minutes and seconds as a string
def total_time_in_hms_get(total_time_ns):
	seconds_raw = total_time_ns / 1000000000
	seconds = round(seconds_raw)
	hours = minutes = 0

	if seconds >= 60:
		minutes = round(seconds / 60)
		seconds = seconds % 60

	if minutes >= 60:
		hours = round(minutes / 60)
		minutes = minutes % 60

	# If the quantum is less than a second, we need show a better resolution. A fractional report matters only when
	# it's less than 1.
	if (not (hours and minutes)) and (seconds_raw < 1 and seconds_raw > 0):
		# Round off to two decimals
		seconds = round(seconds_raw, 2)
	elif (not (hours and minutes)) and (seconds_raw < 60 and seconds_raw > 1):
		# Round off to the nearest integer, if the quantum is less than a minute. A fractional report doesn't matter
		# when it's more than 1.
		seconds = round(seconds_raw)

	return (str(hours) + " hour(s) " if hours else "") + (str(minutes) + " minutes " if minutes else "") + (str(
		seconds) + " seconds")


# Delete all empty directories in the target path, that were created to
# match the source structure
def delete_empty_directories_in_target(dir_destination):
	print(
		"Cleaning up \'" + dir_destination + "\' by recursively deleting empty directories created to match the source path...")
	logging.info(
		"Cleaning up \'" + dir_destination + "\' by recursively deleting empty directories created to match the source path...")

	for dir_name, _, _ in os.walk(dir_destination):
		# Ignore directory not empty errors; nothing can be done about it if we want
		# to retain files relevant to the transcoded audio file. The deletion would
		# hence be silent.
		with suppress(OSError):
			os.removedirs(dir_name)

	print("\nDone cleaning up \'" + dir_destination + "\'\n")
	logging.info("\nDone cleaning up \'" + dir_destination + "\'\n")


# Parse command line arguments and return option and/or values of action
def cmd_line_parse(opt_encode, opt_decode, opt_move_format, opt_percentage):
	# Not required to pass the parameter to dict_transcode_tool_platform_get(), as we're
	# merely retrieving the list of keys for validating the formats to transcode
	_, dict_valid_source, _ = dict_transcode_tool_platform_get()

	parser = argparse.ArgumentParser(
		description = "Transcode and move converted audio files to the destined path. The same directory structure found "
		              "under for the source files will be recreated under the path specified as target. If no "
		              "target was specified, the concerned files will obviously not be relocated, and if one of the "
		              "encode/decode options were specified, the output will default to the source directory.",
		add_help = True)

	parser.add_argument("-s", "--source", required = True, action = "store", default = os.getcwd(),
	                    dest = "source",
	                    help = "Specify a (mandatory) source containing the file to be transcoded and/or relocated (after). "
	                           "The script recurses directories to address concerned files, so a directory is also a valid value.")
	parser.add_argument("-t", "--target", required = False, action = "store",
	                    default = None, dest = "target",
	                    help = "Specify optional destination directory to which transcoded files are to be moved (and "
	                           "other relevant files copied). If not, the transcoded files will be generated in the "
	                           "source directory itself.")
	parser.add_argument("-p", opt_percentage, required = False, action = "store_true",
	                    default = None, dest = "percentage",
	                    help = "Show the percentage of files completed (not the actual data processed; just the files")

	# The user should either be encoding or decoding, not both to avoid ugly scenarios. Hence use a
	# mutually exclusive group of options to handle the case.
	transcode = parser.add_mutually_exclusive_group()
	transcode.add_argument("-e", opt_encode, choices = tuple(dict_valid_source.keys()), required = False,
	                       action = "store",
	                       default = None, dest = "encode_to",
	                       help = "Specify which of the supported formats the source is to be transcoded to")
	transcode.add_argument("-d", opt_decode, choices = tuple(dict_valid_source.keys()), required = False,
	                       action = "store",
	                       default = None, dest = "decode_from",
	                       help = "Specify which of the supported encoded source formats is to be decoded")
	transcode.add_argument("-m", opt_move_format, choices = tuple(dict_valid_source.keys()), required = False,
	                       action = "store",
	                       default = None, dest = "move_format",
	                       help = "Specify which of the supported encoded formats is to be moved to the destination")

	result_parse = parser.parse_args()

	root_source = result_parse.source
	dir_destination = result_parse.target
	encode_to = result_parse.encode_to
	decode_from = result_parse.decode_from
	move_format = result_parse.move_format
	percentage = result_parse.percentage

	return root_source, dir_destination, encode_to, decode_from, move_format, percentage


def process_dir(root_source, dir_destination, dir_destination_original, target, transcode, percentage_gather = False,
                dict_files_failed = False):
	exit_code = 0

	# Set up the same target hierarchy as the source
	if root_source != dir_destination:
		# Let's set up a head directory path right under the destination,
		# to reflect the source's relative hierarchical tree
		dir_destination = os.path.join(os.sep, dir_destination + os.sep, os.path.basename(root_source))

	# Create, if the destination directory doesn't already exist.
	if os.path.exists(dir_destination) or create_directory(dir_destination):
		# Target head directory now exists; proceed

		# Be verbal only if we're about to transcode
		if transcode and (not percentage_gather):
			print("\nCommencing transcoding by recursing into source path \'" + root_source + "\'...\n")
			logging.info("\nCommencing transcoding by recursing into source path \'" + root_source + "\'...\n")

		# Transcode loop to handle converting applicable source files

		# If we were asked to transcode before relocation, oblige
		if transcode:
			# Since we tripped on a directory, walk through for files below
			for source_dir, _, file_names in os.walk(root_source):
				for source_file in file_names:
					# Note: While walking the tree, source_file would only
					# contain the file's name without path. source_dir would
					# contain the path (relative, or absolute, based on what
					# was passed on the command line) of the file in question.
					transcode_source_audio(os.path.join(source_dir, source_file), target, transcode, percentage_gather,
					                       dict_files_failed)

		# Our purpose is only to fetch a total count of files to be transcoded; scoot once done
		if percentage_gather:
			return

		# Nothing to do if the source and destination directories are the same
		if root_source != dir_destination:
			print("\nRelocating transcoded files to the destination \'" + dir_destination + "\'...\n")
			logging.info("\nRelocating transcoded files to the destination \'" + dir_destination + "\'...\n")

			# Relocation loop for moving the actual transcoded files

			# Since we tripped on a directory, walk through for files below
			for source_dir, _, file_names in os.walk(root_source):
				for source_file in file_names:
					# Note: While walking the tree, source_file would only
					# contain the file's name without path. source_dir would
					# contain the path (relative, or absolute, based on what
					# was passed on the command line) of the file in question.
					build_target_and_operate(root_source, source_dir, source_file, dir_destination, target)

			# Ensure the originally received (unmodified) destination is passed
			# for cleaning up empty directories created within the target path
			delete_empty_directories_in_target(dir_destination_original)
	else:
		print("\aNo such target directory - \'" + dir_destination + "\'. Aborting.")
		logging.error("No such target directory - \'" + dir_destination + "\'. Aborting.")

		exit_code = 1

	return exit_code


def process_file(root_source, dir_destination, target, transcode, dict_files_failed):
	# We got a file, move it to its appropriate destination
	exit_code = 0

	# Create, if the destination directory doesn't already exist.
	if os.path.exists(dir_destination) or create_directory(dir_destination):
		# Target head directory now exists; proceed

		# If we were asked to transcode before relocation, oblige
		if transcode:
			transcoded_file = transcode_source_audio(root_source, target, transcode, None, dict_files_failed)

			# If the transcoding was successful, or if we have
			# a transcoded file from before, reassign the actual
			# source format file related variables to reflect the
			# transcoded file
			if os.path.exists(transcoded_file):
				root_source = transcoded_file

		# Nothing to do if the source and destination directories are the same
		if root_source != dir_destination:
			print(
				"\nRelocating transcoded file \'" + transcoded_file + "\' to the destination \'" + dir_destination + "\'...\n")
			logging.info(
				"\nRelocating transcoded file \'" + transcoded_file + "\' to the destination \'" + dir_destination + "\'...\n")

			build_target_and_operate("", "", root_source, dir_destination, target)
	else:
		print("\aNo such target directory - \'" + dir_destination + "\'. Aborting.")
		logging.error("No such target directory - \'" + dir_destination + "\'. Aborting.")

		exit_code = 1

	return exit_code


def statistic_print(transcode, root_source, dir_destination, dict_files_failed):
	if dict_files_failed:
		count_failed_files = len(dict_files_failed.keys())

		print("\n\aHere's a list of " + str(
			count_failed_files) + " files that failed to transcode, with the reason below:\n")
		logging.info("\nHere's a list of " + str(
			count_failed_files) + " files that failed to transcode, with the reason below:\n")

		for key_file in dict_files_failed.keys():
			print(key_file)
			print("Reason for failure: " + dict_files_failed[key_file] + "\n")
			logging.info(key_file)
			logging.info("Reason for failure: " + dict_files_failed[key_file] + "\n")

	if transcode:
		print(
			"\nTotal time taken for successfully transcoding " + str(
				transcode_source_audio.total_count_transcode) + " files: " + total_time_in_hms_get(
				transcode_source_audio.total_time_ns_transcode) + "\n")
		logging.info(
			"\nTotal time taken for successfully transcoding " + str(
				transcode_source_audio.total_count_transcode) + " files: " + total_time_in_hms_get(
				transcode_source_audio.total_time_ns_transcode) + "\n")

	# We never moved files if the source and destination directories are the same, so no point
	# reporting as well
	if root_source != dir_destination:
		# We only move transcoded files; other files relevant to the actual audio file are copied.
		# So the total minus transcoded count will yield the copied count.
		print("Moved (" + str(move_or_copy_file.total_count_moved) + ") and/or copied (" + str(
			move_or_copy_file.total_count - move_or_copy_file.total_count_moved) + ") a total of " + sizeof_fmt(
			move_or_copy_file.total_size) + " from " + str(
			move_or_copy_file.total_count) + " files in " + total_time_in_hms_get(
			build_target_and_operate.total_time_ns_relocate))
		logging.info("Moved (" + str(move_or_copy_file.total_count_moved) + ") and/or copied (" + str(
			move_or_copy_file.total_count - move_or_copy_file.total_count_moved) + ") a total of " + sizeof_fmt(
			move_or_copy_file.total_size) + " from " + str(
			move_or_copy_file.total_count) + " files in " + total_time_in_hms_get(
			build_target_and_operate.total_time_ns_relocate))


# Check if the destination directory has write permission before we begin.
# It's possible the user doesn't specify one, and the source being a read-only
# disc. With the destination defaulting to the source, this is bound to cause
# an exception!
def dir_access_write_check(dir_destination):
	print("\nChecking for write access to the target directory \'" + dir_destination + "\'...")
	logging.info("\nChecking for write access to the target directory \'" + dir_destination + "\'...")

	if os.access(dir_destination, os.W_OK):
		print("Write access for \'" + dir_destination + "\' seems available\n")
		logging.info("Write access for \'" + dir_destination + "\' seems available\n")
	else:
		print(
			"\aThe destination \'" + dir_destination + "\' does not have write permission! Specify one with write access.")
		logging.info(
			"The destination \'" + dir_destination + "\' does not have write permission! Specify one with write access.")


def dir_default_set(root_source):
	dir_destination = None

	if os.path.isdir(root_source):
		# Set the default destination directory as the source directory
		# itself. In all probability and commonness, this is what a user
		# would prefer as default.
		dir_destination = root_source
	# The destination was not specified. Generate our own under the
	# current working directory.
	# dir_destination = os.path.join(os.sep, os.getcwd() + os.sep, os.path.basename(__file__).rpartition(os.extsep)[0])
	else:
		dir_destination = os.path.dirname(root_source)

	print("\nDestination not specified; defaulting to the source \'" + dir_destination + "\' itself")
	logging.warning("\nDestination not specified; defaulting to the source \'" + dir_destination + "\' itself")

	return dir_destination


def cwd_change(dir):
	# Change to the working directory of this Python script. Else, any dependencies will not be found.
	os.chdir(os.path.dirname(os.path.abspath(dir)))

	print("\nChanging working directory to \'" + os.path.dirname(os.path.abspath(dir)) + "\'...\n")
	logging.info(
		"\nChanging working directory to \'" + os.path.dirname(os.path.abspath(dir)) + "\'...\n")


def main(argv):
	exit_code = 0

	if is_supported_platform():
		logging_init()

		opt_encode = "--encode-to"
		opt_decode = "--decode-from"
		opt_move_format = "--move-format"
		opt_percentage = "--percentage-completion"

		root_source, dir_destination, encode_to, decode_from, move_format, percentage_show = cmd_line_parse(opt_encode,
		                                                                                                    opt_decode,
		                                                                                                    opt_move_format,
		                                                                                                    opt_percentage)

		# Take the value for which one of the mutually exclusive options was passed in
		target = encode_to if encode_to else (decode_from if decode_from else move_format)

		if target:
			if move_format and percentage_show:
				print("\aOption \'" + opt_percentage + "\' cannot be applied with option \'" + opt_move_format + "\'")
				logging.info(
					"Option \'" + opt_percentage + "\' cannot be applied with option \'" + opt_move_format + "\'")

				exit_code = 1
			else:
				cwd_change(sys.argv[0])

				# Check if the source drive/directory/file exists
				if os.path.exists(root_source):
					# Remove duplicates from the source path(s)
					# root_source = [*set(root_source)]

					dir_destination_original = dir_destination

					if encode_to:
						transcode = "encode"
					elif decode_from:
						transcode = "decode"
					else:
						transcode = None

					# If the user did not specify the destination, set a default
					if not dir_destination:
						dir_destination = dir_default_set(root_source)

					dict_files_failed = {}

					# if dir_access_write_check(dir_destination):
					# Check if we tripped on a directory
					if os.path.isdir(root_source):
						percentage_gather = False

						if percentage_show:
							# If we are to show a percentage of completion, we need to know how many files are
							# to be transcoded in total
							percentage_gather = True

							# We don't care about the return value, as we're merely gathering a headcount of
							# transcode-worthy source files
							process_dir(root_source, dir_destination, dir_destination_original, target, transcode,
							            percentage_gather, None)
							# Gathering the count needs to be done only once, and was already done above
							percentage_gather = False

						# Now process the actual transcoding
						if process_dir(root_source, dir_destination, dir_destination_original, target, transcode,
						               percentage_gather, dict_files_failed):
							exit_code = 1
					else:
						# We tripped on a file
						if process_file(root_source, dir_destination, target, transcode, dict_files_failed):
							exit_code = 1

					statistic_print(transcode, root_source, dir_destination, dict_files_failed)
				# Slows down the script exit, so disabled for now
				# show_toast("Transcode and/or Move Audio Files for Phone", "Done transcoding and/or moving files")
				else:
					print("\aNo such source directory/file to copy from - \'" + root_source + "\'. Aborting.")
					logging.error("No such source directory/file to copy from - \'" + root_source + "\'. Aborting.")

					exit_code = 1
		else:
			print(
				"\aYou need to specify one of the options: " + opt_encode + "/" + opt_decode + "/" + opt_move_format + ", and its value")
			logging.info(
				"You need to specify one of the options: " + opt_encode + "/" + opt_decode + "/" + opt_move_format + ", and its value")

			exit_code = 1
	else:
		print("\aUnsupported OS")
		logging.error("Unsupported OS")

		exit_code = 1

	return exit_code


if __name__ == '__main__':
	main(sys.argv)
