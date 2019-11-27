from __future__ import absolute_import, unicode_literals

import os
import pkgutil
from abc import ABCMeta, abstractmethod

import six

from .activator import Activator


@six.add_metaclass(ABCMeta)
class ViaTemplateActivator(Activator):
    @abstractmethod
    def templates(self):
        raise NotImplementedError

    def generate(self, creator):
        self._generate(self.replacements(creator), self.templates(), creator.bin_dir)
        if self.flag_prompt is not None:
            creator.pyenv_cfg["prompt"] = self.flag_prompt

    def replacements(self, creator):
        return {
            "__VIRTUAL_PROMPT__": "" if self.flag_prompt is None else self.flag_prompt,
            "__VIRTUAL_ENV__": str(creator.env_dir),
            "__VIRTUAL_NAME__": str(creator.env_name),
            "__BIN_NAME__": str(creator.bin_name),
            "__PATH_SEP__": os.pathsep,
        }

    def _generate(self, replacements, templates, to_folder):
        for template in templates:
            text = pkgutil.get_data(self.__module__, str(template)).decode("utf-8")
            for start, end in replacements.items():
                text = text.replace(start, end)
            (to_folder / template).write_text(text)
