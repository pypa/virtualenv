Activate the environment again from bash and zsh when a ``pydoc`` alias is defined. Since 21.14.9 the alias was expanded
in the ``pydoc`` function definition, so ``source bin/activate`` stopped with a syntax error and did not activate.
