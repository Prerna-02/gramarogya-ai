"""Workforce optimization and scheduling service (NSGA-II).

Implemented in Phase 8 using pymoo. Produces multiple non-dominated rosters
rather than a single opaque score.

Hard constraints: qualification, designation, department capability,
availability, approved leave, max weekly hours, minimum rest, mandatory
coverage.
Soft objectives: minimize understaffing, overtime, fatigue, unequal night
shifts, unequal weekends, and preference violations.

Returns at least three options: service-coverage priority, workforce-fairness
priority, and a balanced recommendation. All rosters remain subject to human
review and approval.
"""
