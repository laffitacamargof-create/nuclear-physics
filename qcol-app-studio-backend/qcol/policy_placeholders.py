"""Explicit placeholders for registered future policies."""

def not_implemented_policy(*args, **kwargs):
    raise NotImplementedError(
        "This policy ID is registered for the architecture roadmap but has no "
        "certified callable implementation in this release."
    )
