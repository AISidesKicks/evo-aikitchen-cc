"""Measurement loop for the EVO harness.

This package is the bench, not the agent. It holds the task corpus, the runner,
the graders, the ledger and the statistics that decide whether a change is worth
keeping. The agent itself is Tau, driven through ``tau_agent.AgentHarness``.

See ``mds/evo-benchmark-evals.md`` for the reasoning behind each piece.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
