import subprocess

CREATE_NO_WINDOW = 0x80000000


def run_cmd(cmd):
    try:
        process = subprocess.Popen(
            cmd,
            universal_newlines=True,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        out, err = process.communicate()  # input disabled
        code = process.returncode
    except OSError as error:
        code, out, err = error.errno, "", error.strerror
        if code == 2 and "file" in err:
            err = str(error)  # FileNotFoundError in Python >= 3.3
    return code, out, err


__all__ = (
    "run_cmd",
    "CREATE_NO_WINDOW",
)
