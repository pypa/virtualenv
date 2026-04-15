# This file must be used with "source bin/activate.xsh" *from xonsh*.
# You cannot run it directly.


class _VirtualEnvActivator:
    """xonsh activation for virtualenv.

    Rendered into ``<venv>/bin/activate.xsh`` by the template in
    ``src/virtualenv/activation/xonsh/`` at generate-time.

    - Project: https://github.com/pypa/virtualenv
    - Template source: https://github.com/pypa/virtualenv/tree/main/src/virtualenv/activation/xonsh
    """

    # Stashed in _OLD_VIRTUAL_{name} when the variable was not set before
    # activation. deactivate treats this as "unset" rather than "restore to
    # this string". Chosen to be vanishingly unlikely as a real value.
    _UNSET_SENTINEL = "__virtualenv_was_not_set__"

    def __init__(self):
        self.env = @.env
        # Variables this activator may save+override; deactivate walks this list.
        self.managed_vars = ("PATH", "PYTHONHOME", "TCL_LIBRARY", "TK_LIBRARY")

    def _backup_name(self, name):
        return f"_OLD_VIRTUAL_{name}"

    def _save(self, name):
        """Stash the current value (or sentinel if unset) so deactivate can undo."""
        backup = self._backup_name(name)
        self.env[backup] = self.env[name] if name in self.env else self._UNSET_SENTINEL

    def _override(self, name, value):
        self._save(name)
        self.env[name] = value

    def _drop(self, name):
        self._save(name)
        self.env.pop(name, None)

    def register_pydoc(self):
        aliases["pydoc"] = ["python", "-m", "pydoc"]

    def unregister_pydoc(self):
        aliases.pop("pydoc", None)

    def activate(self):
        from os.path import join, basename

        aliases["deactivate"] = self.deactivate
        self.deactivate(["nondestructive"])  # wipe any stale state from a prior activation

        $VIRTUAL_ENV = __VIRTUAL_ENV__
        $VIRTUAL_ENV_PROMPT = __VIRTUAL_PROMPT__ or basename($VIRTUAL_ENV)

        self._override("PATH", [join($VIRTUAL_ENV, __BIN_NAME__), *$PATH])
        self._drop("PYTHONHOME")
        for name, value in (("TCL_LIBRARY", __TCL_LIBRARY__), ("TK_LIBRARY", __TK_LIBRARY__)):
            if value:
                self._override(name, value)

        self.register_pydoc()

    def deactivate(self, args=None):
        for name in self.managed_vars:
            backup = self._backup_name(name)
            if backup not in self.env:
                continue
            previous = self.env[backup]
            del self.env[backup]
            if previous == self._UNSET_SENTINEL:
                self.env.pop(name, None)
            else:
                self.env[name] = previous
        for name in ("VIRTUAL_ENV", "VIRTUAL_ENV_PROMPT"):
            self.env.pop(name, None)
        self.unregister_pydoc()
        if args is None or "nondestructive" not in args:
            del aliases["deactivate"]
            try:
                del @.xontrib.virtualenv
            except AttributeError:
                pass


if not hasattr(@, "xontrib"):
    @.xontrib = @.imp.types.SimpleNamespace()
@.xontrib.virtualenv = _VirtualEnvActivator()
@.xontrib.virtualenv.activate()
