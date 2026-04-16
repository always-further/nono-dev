"""Session target alias helpers."""

import re


def candidate_session_names(target):
    """Return exact session names that the target may refer to."""
    names = {target}

    match = re.match(r"^issue-(\d+)$", target)
    if match:
        names.add(f"fix-{match.group(1)}")
        return names

    if re.match(r"^(fix|triage|review|feat|bare)(?:-|$)", target):
        return names

    if target and not target.isdigit():
        names.add(f"feat-{target}")
        names.add(f"bare-{target}")

    return names


def named_matches(target, sessions):
    """Return sessions whose exact name matches the target or its aliases."""
    candidate_names = candidate_session_names(target)
    return [s for s in sessions if s.get("name") in candidate_names]
