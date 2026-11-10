/**
 * @name Delete of a metadata-listed path without a containment check
 * @description A line read from package metadata (top_level.txt, RECORD) is joined onto a directory and the result is
 *              deleted without first checking that it resolves inside the environment, so a crafted entry such as
 *              ../../home removes files outside it. The query accepts a delete only on the branch where a
 *              `root in path.parents` (or `not in`) comparison shows the path is inside.
 * @kind path-problem
 * @problem.severity error
 * @security-severity 7.5
 * @precision high
 * @id virtualenv/uncontained-metadata-delete
 * @tags security
 *       external/cwe/cwe-022
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking

module UncontainedMetadataDeleteConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node node) {
    node.(DataFlow::MethodCallNode).getMethodName() in ["splitlines", "readlines"]
  }

  predicate isSink(DataFlow::Node node) {
    exists(DataFlow::CallCfgNode call, string name |
      name in ["unlink", "remove_file", "safe_delete", "rmtree"]
    |
      call.(DataFlow::MethodCallNode).calls(node, name) and not exists(call.getArg(0))
      or
      call.getFunction().asCfgNode().(NameNode).getId() = name and node = call.getArg(0)
      or
      call.getFunction().(DataFlow::AttrRead).getAttributeName() = name and node = call.getArg(0)
    )
  }

  // safe_delete and remove_file are sinks themselves, so stopping here reports a delete once, at its caller, instead
  // of again inside their bodies
  predicate isBarrierOut(DataFlow::Node node) { isSink(node) }

  // codeql/python-all carries taint across `/` only when an operand traces back to a pathlib constructor call, which
  // Path parameters such as dist and env_dir do not
  predicate isAdditionalFlowStep(DataFlow::Node nodeFrom, DataFlow::Node nodeTo) {
    exists(BinaryExprNode slash |
      slash.getOp() instanceof Div and
      nodeFrom.asCfgNode() = slash.getRight() and
      nodeTo.asCfgNode() = slash
    )
  }

  predicate isBarrier(DataFlow::Node node) {
    exists(
      ConditionBlock guard, CompareNode check, Cmpop op, ControlFlowNode parents, boolean inside
    |
      guard.getLastNode() = check and
      check.operands(_, op, parents) and
      parents.(AttrNode).getName() = "parents" and
      (
        op.getSymbol() = "in" and inside = true
        or
        op.getSymbol() = "not in" and inside = false
      ) and
      guard.controls(node.asCfgNode().getBasicBlock(), inside)
    )
  }
}

module UncontainedMetadataDeleteFlow = TaintTracking::Global<UncontainedMetadataDeleteConfig>;

import UncontainedMetadataDeleteFlow::PathGraph

from UncontainedMetadataDeleteFlow::PathNode source, UncontainedMetadataDeleteFlow::PathNode sink
where UncontainedMetadataDeleteFlow::flowPath(source, sink)
select sink.getNode(), source, sink,
  "$@ is deleted without checking that it stays inside the environment.", source.getNode(),
  "This metadata entry"
