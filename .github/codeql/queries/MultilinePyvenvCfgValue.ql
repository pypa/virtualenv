/**
 * @name Line boundary in a pyvenv.cfg value
 * @description A pyvenv.cfg key or value reaches the file without collapse_line_boundaries(), so a prompt or path that
 *              carries a line boundary adds its own configuration lines when Python reads the file back.
 * @kind path-problem
 * @problem.severity error
 * @security-severity 7.3
 * @precision high
 * @id virtualenv/multiline-pyvenv-cfg-value
 * @tags security
 *       external/cwe/cwe-93
 */

import python
import semmle.python.dataflow.new.DataFlow
import semmle.python.dataflow.new.TaintTracking

predicate inPyEnvCfg(DataFlow::Node node) {
  node.getScope().getScope*().(Class).getName().matches("%PyEnvCfg")
}

module MultilinePyvenvCfgValueConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node node) {
    inPyEnvCfg(node) and node.(DataFlow::AttrRead).getAttributeName() = "content"
  }

  predicate isSink(DataFlow::Node node) {
    exists(DataFlow::MethodCallNode call |
      inPyEnvCfg(call) and call.calls(_, "write_text") and node = call.getArg(0)
    )
  }

  predicate isBarrier(DataFlow::Node node) {
    exists(DataFlow::CallCfgNode call |
      call.getFunction().asExpr().(Name).getId() = "collapse_line_boundaries" and node = call
    )
  }
}

module MultilinePyvenvCfgValueFlow = TaintTracking::Global<MultilinePyvenvCfgValueConfig>;

import MultilinePyvenvCfgValueFlow::PathGraph

from MultilinePyvenvCfgValueFlow::PathNode source, MultilinePyvenvCfgValueFlow::PathNode sink
where MultilinePyvenvCfgValueFlow::flowPath(source, sink)
select sink.getNode(), source, sink, "$@ reaches pyvenv.cfg without collapsing line boundaries.",
  source.getNode(), "This configuration value"
