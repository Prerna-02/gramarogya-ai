"""Resource-planning service.

Implemented in Phase 7. Converts the category-level demand forecast into
operational requirements using explainable rules (not an ML model):
staff by designation/skill, beds by type, medicines/consumables (with safety
stock and lead time), equipment, and ambulance capacity. Compares each
requirement against current availability to flag shortages and surpluses.
"""
