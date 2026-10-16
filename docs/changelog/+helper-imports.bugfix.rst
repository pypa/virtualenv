Keep helper processes for pip, stdlib venv creation, and periodic wheel updates from importing modules through Python's
implicit current-directory entry. Pip helpers retain the selected bootstrap wheel on their import path.
