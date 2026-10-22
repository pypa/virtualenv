/**
 * @name chmod inside a shutil.rmtree error handler
 * @description A function passed as onerror or onexc to shutil.rmtree changes permissions of the path it receives. The
 *              handler runs after a failed delete, when a link may have replaced that path.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id virtualenv/chmod-in-delete-handler
 * @tags security
 *       external/cwe/cwe-732
 */

import python

from Call rmtree, Keyword handler, Function onerror, Call chmod
where
  rmtree.getFunc().(Attribute).getName() = "rmtree" and
  handler = rmtree.getANamedArg() and
  handler.getArg() in ["onerror", "onexc"] and
  handler.getValue().(Name).getId() = onerror.getName() and
  chmod.getScope() = onerror and
  chmod.getFunc().(Attribute).getName() = "chmod"
select chmod, "Permissions change inside a delete error handler passed to rmtree."
