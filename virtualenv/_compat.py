try:
    FileNotFoundError = FileNotFoundError
except NameError:
    FileNotFoundError = OSError
