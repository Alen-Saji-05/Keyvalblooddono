"""HTTP routes, grouped into one blueprint per resource.

Route functions do three things: authorise the caller, validate input against a Pydantic
schema, and hand off to a service. Domain decisions live in ``app.services`` so that
they have exactly one implementation and can be tested without an HTTP request.
"""
