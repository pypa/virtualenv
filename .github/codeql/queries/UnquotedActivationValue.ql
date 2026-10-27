/**
 * @name Unquoted value in an activation script
 * @description A value from an activator's replacements() reaches an activation script template without going through
 *              the activator's quote(), so a crafted prompt or path can run shell commands on activation.
 * @kind path-problem
 * @problem.severity error
 * @security-severity 7.8
 * @precision high
 * @id virtualenv/unquoted-activation-value
 * @tags security
 *       external/cwe/cwe-078
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking

module UnquotedActivationValueConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node node) {
    exists(Function replacements, Return ret, Dict dict |
      replacements.getName() = "replacements" and
      ret.getScope() = replacements and
      ret.getValue() = dict and
      node.asExpr() = dict.getAValue()
    )
  }

  predicate isSink(DataFlow::Node node) {
    exists(DictComp comp, Yield yield, Expr value |
      comp.getScope().(Function).getName() = "substitutions" and
      yield.getScope() = comp.getFunction() and
      value = yield.getValue().(Tuple).getElt(1).getASubExpression*() and
      value.(Name).getVariable() = comp.getNthInnerLoop(0).getTarget().(Tuple).getAnElt().(Name).getVariable() and
      not exists(Call quoted |
        quoted.getFunc().(Attribute).getName() = "quote" and value = quoted.getASubExpression*()
      ) and
      node.asExpr() = value
    )
    or
    exists(Return ret, Dict dict |
      ret.getScope().(Function).getName() = "substitutions" and
      ret.getValue() = dict and
      node.asExpr() = dict.getAValue()
    )
  }

  predicate isBarrier(DataFlow::Node node) {
    exists(DataFlow::MethodCallNode call | call.calls(_, "quote") and node = call)
  }
}

module UnquotedActivationValueFlow = TaintTracking::Global<UnquotedActivationValueConfig>;

import UnquotedActivationValueFlow::PathGraph

from UnquotedActivationValueFlow::PathNode source, UnquotedActivationValueFlow::PathNode sink
where UnquotedActivationValueFlow::flowPath(source, sink)
select sink.getNode(), source, sink, "$@ reaches an activation script without quoting.", source.getNode(),
  "This input"
