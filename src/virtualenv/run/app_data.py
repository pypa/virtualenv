import logging
import os
from argparse import Action, ArgumentError
from tempfile import mkdtemp

from appdirs import user_data_dir

from virtualenv.util.lock import ReentrantFileLock
from virtualenv.util.path import safe_delete


class AppData(object):
    def __init__(self, folder):
        self.folder = ReentrantFileLock(folder)
        self.transient = False

    def __repr__(self):
        return "{}".format(self.folder.path)

    def clean(self):
        logging.debug("clean app data folder %s", self.folder.path)
        safe_delete(self.folder.path)

    def close(self):
        """"""


class TempAppData(AppData):
    def __init__(self):
        super(TempAppData, self).__init__(folder=mkdtemp())
        self.transient = True
        logging.debug("created temporary app data folder %s", self.folder.path)

    def close(self):
        logging.debug("remove temporary app data folder %s", self.folder.path)
        safe_delete(self.folder.path)


class AppDataAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        folder = self._check_folder(values)
        if folder is None:
            raise ArgumentError("app data path {} is not valid".format(values))
        setattr(namespace, self.dest, AppData(folder))

    @staticmethod
    def _check_folder(folder):
        folder = os.path.abspath(folder)
        if not os.path.exists(folder):
            try:
                os.makedirs(folder)
                logging.debug("created app data folder %s", folder)
            except OSError as exception:
                logging.info("could not create app data folder %s due to %r", folder, exception)
                return None
        write_enabled = os.access(folder, os.W_OK)
        if write_enabled:
            return folder
        logging.debug("app data folder %s has no write access", folder)
        return None

    @staticmethod
    def default():
        for folder in AppDataAction._app_data_candidates():
            folder = AppDataAction._check_folder(folder)
            if folder is not None:
                return AppData(folder)
        return None

    @staticmethod
    def _app_data_candidates():
        key = str("VIRTUALENV_OVERRIDE_APP_DATA")
        if key in os.environ:
            yield os.environ[key]
        else:
            yield user_data_dir(appname="virtualenv", appauthor="pypa")


__all__ = (
    "AppData",
    "TempAppData",
    "AppDataAction",
)
