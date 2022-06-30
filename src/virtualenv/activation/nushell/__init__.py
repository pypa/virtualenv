import os
from pathlib import Path

from ..via_template import ViaTemplateActivator


class NushellActivator(ViaTemplateActivator):
    def templates(self):
        yield Path("activate.nu")
        yield Path("deactivate.nu")

    def replacements(self, creator, dest_folder):
        # Due to nushell scoping, it isn't easy to create a function that will
        # deactivate the environment. For that reason a __DEACTIVATE_PATH__
        # replacement pointing to the deactivate.nu file is created

        return {
            "__VIRTUAL_PROMPT__": "" if self.flag_prompt is None else self.flag_prompt,
            "__VIRTUAL_ENV__": str(creator.dest),
            "__VIRTUAL_NAME__": creator.env_name,
            "__BIN_NAME__": str(creator.bin_dir.relative_to(creator.dest)),
            "__PATH_SEP__": os.pathsep,
            "__DEACTIVATE_PATH__": str(Path(dest_folder) / "deactivate.nu"),
        }


__all__ = [
    "NushellActivator",
]
