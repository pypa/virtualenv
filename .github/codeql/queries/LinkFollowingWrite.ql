/**
 * @name Write that follows a link at the destination
 * @description A write goes to its path in place (write_text, write_bytes, open in a write or append mode, or os.open
 *              with O_CREAT and no O_EXCL), so a link planted at the destination after an existence check receives it.
 *              Use write_file, which creates the entry exclusively. The query skips the app-data cache and the three
 *              wheel image modules (base, copy, symlink): they write into virtualenv's own cache, not into the
 *              environment being created.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id virtualenv/link-following-write
 * @tags security
 *       external/cwe/cwe-59
 */

import python

predicate inScope(Location loc) {
  loc.getFile().getRelativePath() != "" and
  not loc.getFile()
      .getRelativePath()
      .regexpMatch("(.*/)?app_data/.*|(.*/)?pip_install/(base|symlink|copy)\\.py")
}

predicate writesInPlace(Call call) {
  call.getFunc().(Attribute).getName() in ["write_text", "write_bytes"]
  or
  call.getFunc().(Name).getId() = "open" and
  call.getAnArg().(StringLiteral).getText().regexpMatch("[wa]b?")
  or
  call.getFunc().(Attribute).getName() = "open" and
  call.getAnArg().(StringLiteral).getText().regexpMatch("[wa]b?") and
  not call.getFunc().(Attribute).getObject().(Name).getId() = "os"
  or
  call.getFunc().(Attribute).getObject().(Name).getId() = "os" and
  call.getFunc().(Attribute).getName() = "open" and
  call.getAnArg().getASubExpression*().(Attribute).getName() = "O_CREAT" and
  not call.getAnArg().getASubExpression*().(Attribute).getName() = "O_EXCL"
}

from Call call
where writesInPlace(call) and inScope(call.getLocation())
select call,
  "Writes in place, so a link at the destination receives the write. Use write_file instead."
