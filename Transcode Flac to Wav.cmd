@echo off
cls
set PATH=%PATH%;"C:\Program Files\Python"
:loop_transcode
IF %1=="" GOTO completed
python "G:\My Drive\Projects\Transcode and Move Audio Files\transcode_and_move_audio_files.py" --source %1 --decode-from flac --percentage-completion
SHIFT
GOTO loop_transcode
:completed
pause