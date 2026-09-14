"""OpenClaw core policy package (Single-Brain policy).

High-level planning lives HERE: intent definitions, DAG building, and the
confirmation gate. The PC side (`bridge/openclaw/`) only resolves elements
and executes gated ops — it never plans.
"""
