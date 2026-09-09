from __future__ import annotations

import logging
import os
from configparser import ConfigParser, Error
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final

from platformdirs import user_config_dir

from .convert import convert

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any

    from .convert import TypeData

_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)


class IniConfig:
    VIRTUALENV_CONFIG_FILE_ENV_VAR: ClassVar[str] = "VIRTUALENV_CONFIG_FILE"
    STATE: ClassVar[dict[bool | None, str]] = {None: "failed to parse", True: "active", False: "missing"}

    section = "virtualenv"

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        env = os.environ if env is None else env
        config_file = env.get(self.VIRTUALENV_CONFIG_FILE_ENV_VAR, None)
        self.is_env_var = config_file is not None
        if config_file is None:
            config_file = Path(user_config_dir(appname="virtualenv", appauthor="pypa")) / "virtualenv.ini"
        else:
            config_file = Path(config_file)
        self.config_file = config_file
        self._cache = {}

        self.has_config_file: bool | None = None
        self.has_virtualenv_section = False
        self.config_parser: Final[ConfigParser] = ConfigParser()
        exception = None
        try:
            self.has_config_file = self.config_file.exists()
            if self.has_config_file:
                self.config_file = self.config_file.resolve()
                self._load()
                self.has_virtualenv_section = self.config_parser.has_section(self.section)
        except (OSError, UnicodeError, Error) as exc:
            self.has_config_file = None
            exception = exc
        if exception is not None:
            _LOGGER.error("failed to read config file %s because %r", config_file, exception)

    def _load(self) -> None:
        with self.config_file.open("rt", encoding="utf-8-sig") as file_handler:
            return self.config_parser.read_file(file_handler)

    def get(self, key: str, as_type: TypeData) -> tuple[Any, str] | None:
        cache_key = key, as_type
        if cache_key in self._cache:
            return self._cache[cache_key]
        try:
            source = "file"
            raw_value = self.config_parser.get(self.section, key.lower())
            value = convert(raw_value, as_type, source)
            result = value, source
        except Exception:  # ruff:ignore[blind-except]
            result = None
        self._cache[cache_key] = result
        return result

    def __bool__(self) -> bool:
        return bool(self.has_config_file) and bool(self.has_virtualenv_section)

    @property
    def epilog(self) -> str:
        return (
            f"\nconfig file {self.config_file} {self.STATE[self.has_config_file]} "
            f"(change{'d' if self.is_env_var else ''} via env var {self.VIRTUALENV_CONFIG_FILE_ENV_VAR})"
        )


__all__ = ["IniConfig"]
