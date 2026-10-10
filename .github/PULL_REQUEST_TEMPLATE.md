### Thanks for contributing, make sure you address all the checklists (for details on how see [development documentation](https://virtualenv.pypa.io/en/latest/development.html#development))

- [ ] ran the linter to address style issues (`tox -e fix`)

- [ ] wrote descriptive pull request text

- [ ] ensured there are test(s) validating the fix

- [ ] added news fragment in `docs/changelog` folder

- [ ] updated/extended the documentation

- [ ] for changes to activation scripts, `pyvenv.cfg`, wheel downloads, app-data or release workflows: explained in the
  PR text which outside input the change handles, such as a path, a prompt or a downloaded file, and how it stops that
  input from running as code. See the
  [security scope](https://github.com/pypa/virtualenv/blob/main/.github/SECURITY.md#scope).

- [ ] ran tests on Python 3.9 and 3.15 (`tox run -e 3.9,3.15`)

- [ ] linked upstream issues beside any temporary interpreter overrides

- [ ] kept the PR in draft until CI passes
