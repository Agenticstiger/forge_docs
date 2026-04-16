# FLUID Forge Overview

FLUID Forge is a declarative framework for defining data products in a single contract and then validating, planning, and applying them across providers.

Core flow:

```text
contract.fluid.yaml -> fluid validate -> fluid plan -> fluid apply
```

The contract can express:

- product identity and ownership
- schema and exposure definitions
- build patterns and transformations
- data quality expectations
- governance and access rules
- provider-specific bindings
- optional sovereignty and AI governance
- optional semantic truth modeling in FLUID `0.7.2`

For this GPT packet, the important behavior is:

- draft from a compact reference set
- ask provider-specific questions
- avoid invented governance
- require validation and plan review before finality
