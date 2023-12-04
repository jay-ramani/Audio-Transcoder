# Audio Transcoder

## What This Is
A Python script that transcodes audio files between various formats. While we have scores of transcoders out there, this script is fine tuned to get the best tradeoff between quality and size for transcoding to Opus format. Opus especially, is very high in quality at highly compressed sizes. This is especially important with storage constrained devices like mobile phones, where the trend is for manufacturers to do away with high capacity extendable local storage (read: u/SD cards!) and force users to switch to cloud providers.

* Encoding to Opus from
  - Wav
  - AIFF
  - FLAC
  - OGA
  - PCM

* Decode from Opus to Wav

* Encoding to FLAC from
  - Wav
  - AIFF
  - rf64
  - w64
 
* Decode from FLAC to Wav

Tip: Tag source files, so the transcoded files don't require re-tagging.

**Note**: Use a Python 3.6 environment or above to execute the script.

## External Tools Used
Obviously, [Python](https://www.python.org) is used to interpret the script itself. The transcoding code uses external tools ('[opus-tools](https://opus-codec.org/downloads/)' and '[flac & metaflac](https://xiph.org/flac/documentation_tools.html)').

* `opusenc`: used to encode a compatible source format to Opus
* `opusdec`: used to decode Opus to Wav
* `opusinfo`: used to retrieve metadata from Opus
* `flac`: used to encode and decode to and from FLAC
* `metaflac` to edit FLAC metadata

## Where to Download the External Tools From
* Binaries of opus-tools are available at https://archive.mozilla.org/pub/opus/win32/opus-tools-0.2-opus-1.3.zip
* Binaries of flac are available at https://ftp.osuosl.org/pub/xiph/releases/flac/flac-1.4.3-win.zip

## Pre-requisites for Use
Ensure you have these external tools installed and define the path appropriately for the required binaries (`opusenc`, `opusdec`, and `flac`) through the following variables under the respective Operating System checks in the function `dict_transcode_tool_platform_get()` in transcode_and_move_audio_files.py:

```
dict_encode_tool_windows
dict_decode_tool_windows
dict_encode_tool_linux
dict_decode_tool_linux
```

For example:
```python
	# Point to encoding binaries on Windows for supported formats
	dict_encode_tool_windows = {
		"opus": ("opusenc.exe", options_encode_opus),
		"flac": ("flac.exe", options_encode_flac)
	}
	dict_decode_tool_windows = {
		"opus": ("opusdec.exe", options_decode_opus),
		"flac": ("flac.exe", options_decode_flac)
	}

	# Point to decoding binaries on Linux for supported formats
	dict_encode_tool_linux = {
		"opus": ("/usr/bin/opusenc", options_encode_opus),
		"flac": ("/usr/bin/flac", options_encode_flac)
	}
	dict_decode_tool_linux = {
		"opus": ("/usr/bin/opusdec", options_decode_opus),
		"flac": ("/usr/bin/flac", options_decode_flac)
	}
```
**Note**: Windows path separators have to be double escaped using another backslash, as shown in the example above. On Linux, unless these tools have already been added to the PATH environment variable, you would have to update the environment, or manually feed the path. Also, though the binaries could point to any path via these variables, I find it easier extracting them to the same directory as the script.

If you'd like a tooltip notification on Windows 10 and above, install [win10toast](https://pypi.org/project/win10toast/) with `pip install win10toast`. Tooltips on Linux are supported natively in the script (thanks to `notify-send`).

## How to Batch Process/Use on Single Files
### Batch Processing Recursively/A Selection Through a Simple Right-Click
  On Windows, in the Run window, type "shell:sendto" and copy the files called "Transcode Flac to Wav.cmd", "Transcode to Flac.cmd" and "Transcode to Opus.cmd" into the directory that opens (this is where your items that show up on right-clicking and choosing 'Send To' appear). Edit these files to reflect as below for the 3rd and 6th lines:

```batch
  @echo off
  cls
  set PATH=%PATH%;C:\Python
  :loop_tag
  IF %1=="" GOTO completed
  python "G:\My Drive\Projects\Transcode and Move Audio Files\transcode_and_move_audio_files.py" --source %1 --decode-from flac --percentage-completion
  SHIFT
  GOTO loop_tag
  :completed
```
  Note: In the 3rd line above, ensure you set the path correctly for your Python installation, and in the 6th line, the path to where you download this Python script to.

  Once you're done with the above, all you have to do is right-click on any directory (or even a selection of them!) containing the source audio files, use 'Send To' to send to the command name saved above ('Transcode Flac to Wav.cmd', as in the example above), and the script will recursively scan through directories and transcode your source auddio files to the destination format. The source and destination formats are listed at the beginning of this document.

  I've included this all the .cmd files, so feel free to edit and set parameters according to your installation.

  Since Linux (or any Unix like OS) use varies with a lot of graphical managers, I'm not going to delve into getting verbose here; you can refer your distribution's documentation to figure it out.

### Batch Processing Recursively Through a Command

Here's an example of transcoding a directory containing the source audio format to be converted to Opus:
```
  python "C:\Users\<user login>\Transcode and Move Audio Files\transcode_and_move_audio_files.py" --percentage-completion --source <path to a directory containing source audio files> <path to another directory...> <you get the picture!> --encode-to-opus
```
### Tagging Single Files
  If you'd prefer going Hans Solo, use the command below to act on a single file:
```
  python "G:\My Drive\Projects\Transcode and Move Audio Files\transcode_and_move_audio_files.py" --source <source audio file> --encode-to opus
```
## Options
* `--source`, or `-s`: Specify a mandatory source directory or file to be transcoded
* `--target`, or `-t`: Specify an optional target directory to which transcoded files will be relocated. If the source directory contained any file that has an extension "mpc", "jpg", "jpeg", "png", "pls", "rtf", "txt" or "accurip", these will be copied to the target directory as well, since they might be relevant to some users. This inclusion list can be edited in the function `main_and_relevant_files_for_audio_get()`.
* `--encode-to`, or `-e`: Specify which of the supported formats the source is to be transcoded to
* `--decode-from`, or `-d`: Specify which of the supported encoded source formats is to be decoded
* `--move-format`, or `-m`: Specify which of the supported encoded formats is to be moved to the destination
* `--percentage-completion`, or `-p`: Report the percentage of completion. This comes handy when tagging a large number of files recursively (either with the right-click 'Send To' option, or through the command line). You might want to skip this option if you'd like the script to execute faster.
* `--help`, or `-h`: Usage help for command line options

## Reporting a Summary
At the end of its execution, the script presents a summary of files transcoded, failures (if any) and time taken. Again, this comes in handy when dealing with a large number of files.

## Logging
For a post-mortem, or simply quenching curiosity, a log file is generated with whatever is attempted by the script. This log is generated in the local application data directory (applicable to Windows), under my name (Jay Ramani). For example, this would be `C:\Users\<user login>\AppData\Local\Jay Ramani\transcode_and_move_audio_files`.

## TODO (What's Next)
A GUI front-end to make things easy

## Known Issues

## Testing and Reporting Bugs
The transcoder has been tested on Windows 10, 11 and on Manjaro Linux (XFCE). Would be great if someone can help with testing on other platforms and provide feedback.

To report bugs, use the issue tracker with GitHub.

## End User License Agreement
This software is released under the GNU General Public License version 3.0 (GPL3), and you agree to this license for any use of the software

## Disclaimer
Though not possible, I am not responsible for any corruption of your files. Needless to say, you should always backup before trying anything on your precious data.
