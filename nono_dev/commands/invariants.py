"""Invariants command group: validate (and, later, stats / check-sources / matcher).

Reads `invariants.yaml` (or .json) and validates against the shipped JSON
Schema at `nono_dev/schemas/invariants.schema.json`.

Zero external dependencies by default: the `validate` subcommand only
imports PyYAML when the input file is YAML. Users who stick to JSON
invariants don't need PyYAML installed. YAML users get a clear install
hint when it's missing; this keeps nono-dev's "stdlib-only at install"
invariant intact for the common case.

We do NOT depend on jsonschema. The schema we ship uses a narrow subset
of JSON Schema (required/additionalProperties/patterns/enum/anyOf/items/
minLength/maxLength/minItems/uniqueItems/format=date), so a targeted
validator -- about 120 lines -- covers everything the schema expresses.
A general JSON Schema implementation would be 5-10x that and bring a
hard dependency we don't need.
"""

import importlib.resources
import json
import os
import re
import sys
from datetime import date

from nono_dev import style


# -- argparse wiring ---------------------------------------------------------


def _invariants_help(_args):
    print()
    print(style.banner("  nono-dev invariants"))
    print()
    print(style.help_row("invariants validate", "[path]", "Validate an invariants file against the schema"))
    print()
    sys.exit(0)


def add_parser(subparsers):
    inv_parser = subparsers.add_parser("invariants", help="Manage the invariants.yaml file")
    inv_sub = inv_parser.add_subparsers(dest="invariants_command")
    inv_parser.set_defaults(func=_invariants_help)

    # validate
    val_parser = inv_sub.add_parser(
        "validate",
        help="Validate an invariants file against the JSON Schema",
    )
    val_parser.add_argument(
        "path", nargs="?", default=None,
        help="Path to invariants file (default: docs/invariants.yaml, fallback proj/invariants.yaml)",
    )
    val_parser.add_argument(
        "--schema", default=None,
        help="Path to schema file (default: shipped nono_dev/schemas/invariants.schema.json)",
    )
    val_parser.set_defaults(func=run_validate)


# -- locate shipped schema ---------------------------------------------------


def _shipped_schema_path():
    """Absolute path to the shipped JSON Schema.

    Uses `importlib.resources` so this works for both editable installs
    (where nono_dev.schemas resolves to a real directory) and wheel
    installs (where it may resolve via a loader).
    """
    ref = importlib.resources.files("nono_dev.schemas").joinpath(
        "invariants.schema.json",
    )
    path = str(ref)
    if os.path.isfile(path):
        return path
    # Fallback: copy out of the package to a temp file (wheel install edge).
    import tempfile
    content = ref.read_text(encoding="utf-8")
    fd, tmp = tempfile.mkstemp(suffix=".json", prefix="invariants-schema-")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return tmp


# -- file loading (yaml or json) ---------------------------------------------


def _load_data(path):
    """Parse YAML or JSON at `path`. Returns parsed Python data.

    YAML is optional: only needed if the user's file has a YAML extension.
    We keep PyYAML off the hard-dependency list so users who never touch
    invariants don't pay for an install.
    """
    ext = os.path.splitext(path)[1].lower()
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if ext in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError:
            print(
                style.error(
                    "PyYAML is required to validate YAML invariants files. "
                    "Install with:\n"
                    "  uv tool install --with pyyaml nono-dev\n"
                    "  # or, globally:\n"
                    "  pipx inject nono-dev pyyaml\n"
                    "  # or, ad hoc:\n"
                    "  pip install --user pyyaml"
                ),
                file=sys.stderr,
            )
            sys.exit(2)
        return yaml.safe_load(text)
    if ext == ".json":
        return json.loads(text)
    # Unknown extension: try JSON first (works for plain dicts/lists in JSON),
    # then fall back to YAML if available. Most real-world files will have
    # a conventional extension, so this branch is defensive, not a hot path.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError:
            print(
                style.error(
                    f"cannot determine format of {path} (not JSON, and PyYAML not installed)"
                ),
                file=sys.stderr,
            )
            sys.exit(2)
        return yaml.safe_load(text)


def _load_schema(path):
    """Parse the schema JSON, for display/version sanity only.

    The actual validator hardcodes the constraints -- so we don't need
    to *interpret* the schema at runtime. Loading it lets us surface its
    $id / title in the success message.
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# -- targeted validator ------------------------------------------------------
#
# The shipped schema uses a narrow subset of JSON Schema keywords:
#   type, required, additionalProperties, enum, pattern, minLength,
#   maxLength, minItems, uniqueItems, items, anyOf, format=date.
# Rather than implement a general validator, we encode the schema's
# actual constraints directly. Every rule below maps 1:1 to a line in
# the .schema.json. If the schema changes, update this function.


_ID_RE = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")
_SUBSYSTEM_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_TAG_RE = _SUBSYSTEM_RE  # same pattern
_SOURCE_LOCAL_RE = re.compile(
    r"^[A-Za-z0-9_./-]+\.(md|mdx|adoc|rst|txt)(#[A-Za-z0-9_-]+)?$",
)
_SOURCE_URL_RE = re.compile(r"^https?://")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_REQUIRED_FIELDS = ("id", "subsystems", "statement", "source", "severity")
_ALLOWED_FIELDS = set(_REQUIRED_FIELDS) | {
    "added", "last_reviewed", "tags", "related",
}
_SEVERITIES = ("high", "medium", "low")


def _validate(data):
    """Return a list of human-readable error messages. Empty == valid."""
    errors = []

    if not isinstance(data, list):
        return ["top-level must be an array of invariant entries"]
    if len(data) < 1:
        errors.append("at least one invariant entry is required")

    seen_ids = set()
    for i, entry in enumerate(data):
        prefix = f"entry[{i}]"
        if isinstance(entry, dict):
            # Prefer `id` in the prefix when available -- easier to locate.
            eid = entry.get("id")
            if isinstance(eid, str) and eid:
                prefix = f"entry[{i}] ({eid!r})"

        _validate_entry(entry, prefix, seen_ids, errors)

    return errors


def _validate_entry(entry, prefix, seen_ids, errors):
    if not isinstance(entry, dict):
        errors.append(f"{prefix}: must be an object, got {type(entry).__name__}")
        return

    # Required fields
    missing = [f for f in _REQUIRED_FIELDS if f not in entry]
    if missing:
        errors.append(f"{prefix}: missing required field(s): {', '.join(missing)}")

    # Unknown / misspelled fields (additionalProperties: false)
    unknown = sorted(set(entry.keys()) - _ALLOWED_FIELDS)
    if unknown:
        errors.append(f"{prefix}: unknown field(s): {', '.join(unknown)}")

    # id
    id_val = entry.get("id")
    if "id" in entry:
        if not isinstance(id_val, str):
            errors.append(f"{prefix}.id: must be string, got {type(id_val).__name__}")
        else:
            if not _ID_RE.match(id_val):
                errors.append(
                    f"{prefix}.id: {id_val!r} must match /^[a-z][a-z0-9-]*[a-z0-9]$/ "
                    f"(kebab-case)"
                )
            if not (3 <= len(id_val) <= 60):
                errors.append(f"{prefix}.id: length must be 3-60 (got {len(id_val)})")
            if id_val in seen_ids:
                errors.append(f"{prefix}.id: duplicate id {id_val!r}")
            else:
                seen_ids.add(id_val)

    # subsystems
    subs = entry.get("subsystems")
    if "subsystems" in entry:
        if not isinstance(subs, list):
            errors.append(f"{prefix}.subsystems: must be an array")
        else:
            if len(subs) < 1:
                errors.append(f"{prefix}.subsystems: must have at least 1 item")
            if len(set(map(repr, subs))) != len(subs):
                errors.append(f"{prefix}.subsystems: items must be unique")
            for j, s in enumerate(subs):
                if not isinstance(s, str):
                    errors.append(f"{prefix}.subsystems[{j}]: must be string")
                    continue
                if not _SUBSYSTEM_RE.match(s):
                    errors.append(
                        f"{prefix}.subsystems[{j}]: {s!r} must match "
                        f"/^[a-z][a-z0-9_-]*$/"
                    )
                if not (2 <= len(s) <= 40):
                    errors.append(
                        f"{prefix}.subsystems[{j}]: length must be 2-40 (got {len(s)})"
                    )

    # statement
    stmt = entry.get("statement")
    if "statement" in entry:
        if not isinstance(stmt, str):
            errors.append(f"{prefix}.statement: must be string")
        elif not (20 <= len(stmt) <= 1500):
            errors.append(
                f"{prefix}.statement: length must be 20-1500 (got {len(stmt)})"
            )

    # source
    src = entry.get("source")
    if "source" in entry:
        if not isinstance(src, str):
            errors.append(f"{prefix}.source: must be string")
        else:
            if not (5 <= len(src) <= 300):
                errors.append(f"{prefix}.source: length must be 5-300 (got {len(src)})")
            if not (_SOURCE_LOCAL_RE.match(src) or _SOURCE_URL_RE.match(src)):
                errors.append(
                    f"{prefix}.source: {src!r} must be 'path/to/doc.md[#anchor]' "
                    f"or 'https://...'"
                )

    # severity
    sev = entry.get("severity")
    if "severity" in entry:
        if sev not in _SEVERITIES:
            errors.append(
                f"{prefix}.severity: {sev!r} must be one of {list(_SEVERITIES)}"
            )

    # Optional: added, last_reviewed (ISO date)
    for field in ("added", "last_reviewed"):
        val = entry.get(field)
        if val is None or field not in entry:
            continue
        if not isinstance(val, str) or not _DATE_RE.match(val):
            errors.append(f"{prefix}.{field}: must be 'YYYY-MM-DD' string")
            continue
        # Also verify the date parses (e.g. reject 2024-13-45)
        try:
            date.fromisoformat(val)
        except ValueError as exc:
            errors.append(f"{prefix}.{field}: invalid date {val!r}: {exc}")

    # Optional: tags
    tags = entry.get("tags")
    if "tags" in entry:
        if not isinstance(tags, list):
            errors.append(f"{prefix}.tags: must be an array")
        else:
            if len(set(map(repr, tags))) != len(tags):
                errors.append(f"{prefix}.tags: items must be unique")
            for j, t in enumerate(tags):
                if not isinstance(t, str):
                    errors.append(f"{prefix}.tags[{j}]: must be string")
                    continue
                if not _TAG_RE.match(t):
                    errors.append(
                        f"{prefix}.tags[{j}]: {t!r} must match /^[a-z][a-z0-9_-]*$/"
                    )

    # Optional: related
    rel = entry.get("related")
    if "related" in entry:
        if not isinstance(rel, list):
            errors.append(f"{prefix}.related: must be an array")
        else:
            if len(set(map(repr, rel))) != len(rel):
                errors.append(f"{prefix}.related: items must be unique")
            for j, r in enumerate(rel):
                if not isinstance(r, str):
                    errors.append(f"{prefix}.related[{j}]: must be string")
                    continue
                if not _ID_RE.match(r):
                    errors.append(
                        f"{prefix}.related[{j}]: {r!r} must match the id "
                        f"pattern /^[a-z][a-z0-9-]*[a-z0-9]$/"
                    )


# -- resolve input path ------------------------------------------------------


def _resolve_input_path(explicit):
    """Pick the invariants file to validate.

    Resolution order:
      1. Explicit `--` positional argument
      2. `docs/invariants.yaml`      (canonical)
      3. `docs/invariants.json`      (JSON users)
      4. `proj/invariants.yaml`      (draft-phase fallback)
      5. `proj/invariants.json`

    Errors if none exist.
    """
    if explicit:
        if not os.path.isfile(explicit):
            print(style.error(f"no such file: {explicit}"), file=sys.stderr)
            sys.exit(2)
        return explicit

    for candidate in (
        "docs/invariants.yaml",
        "docs/invariants.json",
        "proj/invariants.yaml",
        "proj/invariants.json",
    ):
        if os.path.isfile(candidate):
            return candidate

    print(
        style.error(
            "no invariants file found. Looked for:\n"
            "  docs/invariants.yaml\n"
            "  docs/invariants.json\n"
            "  proj/invariants.yaml\n"
            "  proj/invariants.json\n"
            "Pass an explicit path to validate elsewhere:\n"
            "  nd invariants validate path/to/invariants.yaml"
        ),
        file=sys.stderr,
    )
    sys.exit(2)


# -- command handler ---------------------------------------------------------


def run_validate(args):
    input_path = _resolve_input_path(args.path)
    schema_path = args.schema or _shipped_schema_path()

    if not os.path.isfile(schema_path):
        print(style.error(f"schema not found: {schema_path}"), file=sys.stderr)
        sys.exit(2)

    # We load the schema mostly for display purposes; the validator uses
    # hardcoded constraints. This keeps the error from a corrupt schema
    # file obvious rather than silent.
    try:
        schema = _load_schema(schema_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(style.error(f"could not load schema {schema_path}: {exc}"), file=sys.stderr)
        sys.exit(2)

    try:
        data = _load_data(input_path)
    except (OSError,) as exc:
        print(style.error(f"could not read {input_path}: {exc}"), file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(style.error(f"{input_path}: invalid JSON: {exc}"), file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # yaml.YAMLError, etc.
        print(style.error(f"{input_path}: parse error: {exc}"), file=sys.stderr)
        sys.exit(2)

    errors = _validate(data)

    if errors:
        print(style.error(f"{input_path}: {len(errors)} validation error(s)"), file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        sys.exit(1)

    count = len(data) if isinstance(data, list) else 0
    title = schema.get("title", "Invariants")
    print(style.success(f"{input_path}: {count} entries valid ({title})"))
    print(f"  {style.label('schema:')} {style.value(schema_path)}")
