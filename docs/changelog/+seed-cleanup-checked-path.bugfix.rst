Delete the checked path when replacing seed packages, and serialize installation into a shared environment so a
concurrent package cannot redirect metadata cleanup outside it.
