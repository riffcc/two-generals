import Lake
open Lake DSL

package «two-generals-proof» {
  -- add package configuration options here
}

require mathlib from git
  "https://github.com/leanprover-community/mathlib4" @ "v4.14.0"

@[default_target]
lean_lib «TwoGenerals» {
  -- add library configuration options here
}

lean_lib «NetworkModel» {
  -- Layer 2: Probabilistic network reliability
}

lean_lib «TimeoutMechanism» {
  -- Layer 3: Timeout-based coordinated abort
}

lean_lib «MainTheorem» {
  -- Layer 4: Complete integration
}

lean_lib «ExtremeLoss» {
  -- Layer 5: Extreme loss scenario (99.9999% loss, 1000 msg/sec, 18 hours)
}
