"""Patient facility-ranking service.

Implemented in Phase 11. Ranks facilities for the patient/public interface using
service capability, verified doctor availability, estimated waiting time,
travel time, and emergency status.

Guardrails: does NOT diagnose illness; only provides facility guidance and
emergency contact support. Never exposes individual staff schedules or
sensitive hospital information. Surfaces the data-last-verified timestamp.
"""
