Fix ``--symlink-app-data`` on Windows without long path support when the app-data folder left room for the seed wheel
files but not for the ones ``compileall`` writes into the symlink image, so building the image failed. The check for
whether the image needs its 8.3 short path now also counts the compiled files and the temporary files they are written
through.
