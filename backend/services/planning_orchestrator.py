"""Planning orchestrator.

Implemented in Phase 9. Backs POST /api/planning-runs: creates a
`planning_run_id`, then calls the services in order and stores every output
under that shared id.

    create forecast -> calculate resources -> generate roster -> check emergency

Services are invoked as in-process function calls (the backend never calls its
own HTTP endpoints). Run status is tracked as: queued, running, completed,
failed. If a downstream module fails, prior valid outputs are preserved.
"""
