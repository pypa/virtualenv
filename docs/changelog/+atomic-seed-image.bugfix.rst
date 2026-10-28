Build the seed wheel image in a staging folder and move it into place only once it is complete, so an extraction that
fails part way, for example on a full disk, after a killed process or on a path over the Windows length limit, no longer
leaves a partial image that later runs seed as a pip without ``METADATA``, ``RECORD`` or ``INSTALLER``.
