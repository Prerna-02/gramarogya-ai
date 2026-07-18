"""Emergency coordination service.

Implemented in Phase 12. Combines the forecasted surge with bed/staff/medicine/
equipment capacity and applies transparent thresholds for Watch / High /
Critical status. Ranks nearby facilities by road travel time, capability,
readiness, and referral capacity, then drafts alerts (scenario, expected surge,
requested support, response deadline) and tracks their status
(draft, sent, acknowledged, accepted, partially accepted, declined).

A human emergency officer remains responsible for sending external alerts.
"""
