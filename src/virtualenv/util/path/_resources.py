from contextlib import contextmanager

from ._pathlib import Path


@contextmanager
def path_accessor(path):
    if isinstance(path, Path):
        yield path
    else:
        # Assume `virtualenv.util.resources.ResourcePath` but don't import it to save time
        with path.as_path() as p:
            yield p
