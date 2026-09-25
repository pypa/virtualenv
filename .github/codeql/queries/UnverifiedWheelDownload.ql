/**
 * @name Downloaded wheel used without a digest check
 * @description A function runs pip download without calling verify_wheel_digest(), so a compromised index or mirror can
 *              hand virtualenv a wheel that it then caches and installs into new environments.
 * @kind problem
 * @problem.severity error
 * @security-severity 7.5
 * @precision high
 * @id virtualenv/unverified-wheel-download
 * @tags security
 *       external/cwe/cwe-494
 */

import python

from Function download, Call popen
where
  popen.getScope() = download and
  popen.getFunc().(Name).getId() = "Popen" and
  exists(StringLiteral subcommand | subcommand.getScope() = download and subcommand.getText() = "download") and
  not exists(Call verify |
    verify.getScope() = download and verify.getFunc().(Name).getId() = "verify_wheel_digest"
  )
select popen, "This pip download in $@ never calls verify_wheel_digest().", download, download.getName()
