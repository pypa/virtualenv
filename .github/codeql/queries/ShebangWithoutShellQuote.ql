/**
 * @name Shebang built without the shell-safe helper
 * @description A ScriptMaker subclass overrides _build_shebang without calling shell_shebang(), so the script's first
 *              line carries an interpreter path with spaces or shell syntax unquoted.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id virtualenv/shebang-without-shell-quote
 * @tags security
 *       external/cwe/cwe-78
 */

import python

from Function build, Class owner
where
  build.getName() = "_build_shebang" and
  owner = build.getScope() and
  owner.getABase().(Name).getId() = "ScriptMaker" and
  not exists(Call call | call.getScope() = build and call.getFunc().(Name).getId() = "shell_shebang")
select build, "_build_shebang does not quote the interpreter path with shell_shebang()."
