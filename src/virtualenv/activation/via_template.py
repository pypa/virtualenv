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
            text = pkgutil.get_data(self.__module__, str(template)).decode("utf-8")
            for start, end in replacements.items():
                text = text.replace(start, end)
            with open(six.ensure_text(str(to_folder / template)), 'wb') as file_handler:
                file_handler.write(text.encode('utf-8'))
