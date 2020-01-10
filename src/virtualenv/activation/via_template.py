from __future__ import absolute_import, unicode_literals

import os
import sys
from abc import ABCMeta, abstractmethod

import six

from .activator import Activator

if sys.version_info >= (3, 7):
    from importlib.resources import read_text
else:
    from importlib_resources import read_text


@six.add_metaclass(ABCMeta)
class ViaTemplateActivator(Activator):
    @abstractmethod
    def templates(self):
        raise NotImplementedError

    def generate(self, creator):
        dest_folder = creator.bin_dir
        self._generate(self.replacements(creator, dest_folder), self.templates(), dest_folder)
        if self.flag_prompt is not None:
            creator.pyenv_cfg["prompt"] = self.flag_prompt

    def replacements(self, creator, dest_folder):
        return {
            "__VIRTUAL_PROMPT__": "" if self.flag_prompt is None else self.flag_prompt,
            "__VIRTUAL_ENV__": six.ensure_text(str(creator.dest_dir)),
            "__VIRTUAL_NAME__": creator.env_name,
            "__BIN_NAME__": six.ensure_text(str(creator.bin_name)),
            "__PATH_SEP__": os.pathsep,
        }

    def _generate(self, replacements, templates, to_folder):
        for template in templates:
            text = self.instantiate_template(replacements, template)
            (to_folder / template).write_text(text, encoding="utf-8")

    def instantiate_template(self, replacements, template):
        # read text and do replacements
        text = read_text(self.__module__, str(template), encoding="utf-8", errors="strict")
        for start, end in replacements.items():
            text = text.replace(start, end)
        return text
