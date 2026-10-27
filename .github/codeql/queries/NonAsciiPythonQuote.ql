/**
 * @name Non-ASCII-unsafe quoting in a Python or xonsh activator
 * @description The quote() of an activator whose script Python or xonsh reads as text uses repr() instead of ascii(),
 *              so the reader decodes a non-ASCII value under an encoding the writer did not assume.
 * @kind problem
 * @problem.severity warning
 * @precision high
 * @id virtualenv/non-ascii-python-quote
 * @tags security
 *       external/cwe/cwe-116
 */

import python

from Function quote, Call repr
where
  quote.getName() = "quote" and
  quote.getScope().(Class).getName() in ["XonshActivator", "PythonActivator"] and
  repr.getScope() = quote and
  repr.getFunc().(Name).getId() = "repr"
select repr, "quote() of a Python-readable activator uses repr() instead of ascii()."
