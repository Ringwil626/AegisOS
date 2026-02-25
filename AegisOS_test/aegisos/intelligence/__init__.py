"""AegisOS Intelligence Layer - Phase6 Governed Optimization Loop.

This module provides offline analysis and optimization capabilities.
It is a "staff office", not a "frontline soldier" - it only reads data,
never executes tasks or modifies runtime directly.

Components:
- analyzer: Behavior observer (read-only)
- evaluator: Decide if optimization is warranted
- optimizer: Generate candidate strategies (proposals only)
- policy: Strategy configuration and versioning

Philosophy:
- Offline decision + Online execution
- AI proposes, system validates, human approves
- Shadow execution before production
- Strategy versioning with active/shadow/retired states
"""
