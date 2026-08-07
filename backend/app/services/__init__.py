"""Domain logic.

Anything that decides something - who is eligible, what a request's status should be,
what the network summary reports - lives here rather than in a route handler. Two of
these rules have more than one caller: the eligibility predicate is needed by the donor
search filter, by the broadcast selector, and by the summary count, and if it were
written inline in each it would be written three times and drift.
"""
