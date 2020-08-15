from __future__ import absolute_import, unicode_literals

from virtualenv.info import IS_WIN
from virtualenv.util.path import Path
from virtualenv.util.six import ensure_text

from ..via_template import ViaTemplateActivator


class BashActivator(ViaTemplateActivator):
    def generate(self, creator):
        generated = super(BashActivator, self).generate(creator)
        if IS_WIN:
            _convert_to_unix_line_endings(generated)
        return generated

    def templates(self):
        yield Path("activate.sh")

    def as_name(self, template):
        return template.stem


def _convert_to_unix_line_endings(generated):
    WINDOWS_LINE_ENDING = b"\r\n"
    UNIX_LINE_ENDING = b"\n"

    for file_path in generated:
        with open(ensure_text(str(file_path)), "rb") as open_file:
            content = open_file.read()

        content = content.replace(WINDOWS_LINE_ENDING, UNIX_LINE_ENDING)

        with open(ensure_text(str(file_path)), "wb") as open_file:
            open_file.write(content)
