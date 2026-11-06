Unset ``PYTHONHOME`` when activating from csh, and restore it on ``deactivate``, as the other activators already do.
With it still set, the environment's interpreter looked for the standard library under the old prefix and failed to
start.
