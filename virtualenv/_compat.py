from __future__ import absolute_import, division, print_function

try:
    FileNotFoundError = FileNotFoundError
except NameError:  # pragma: no cover
    FileNotFoundError = OSError


# Python 2.6 does not have check_output, so we'll backport this just for
# Python 2.6
import subprocess
try:
    from subprocess import check_output
except ImportError:  # pragma: no cover
    def check_output(*popenargs, **kwargs):
        if "stdout" in kwargs:
            raise ValueError(
                "stdout argument not allowed, it will be overridden."
            )
        if "input" in kwargs:
            if "stdin" in kwargs:
                raise ValueError(
                    "stdin and input arguments may not both be used."
                )
            inputdata = kwargs["input"]
            del kwargs["input"]
            kwargs["stdin"] = subprocess.PIPE
        else:
            inputdata = None
        process = subprocess.Popen(
            *popenargs,
            stdout=subprocess.PIPE,
            **kwargs
        )
        try:
            output, unused_err = process.communicate(inputdata)
        except:
            process.kill()
            process.wait()
            raise
        retcode = process.poll()
        if retcode:
            raise subprocess.CalledProcessError(retcode, output)
        return output
