Delete app data trees holding files past the 260 character path limit on Windows without long path support.
``--reset-app-data`` failed with ``WinError 145`` after removing part of the seed ``pip`` image, so later environments
got a ``pip`` that could not be imported, and the staging folder of a killed seed image build failed every later run.
