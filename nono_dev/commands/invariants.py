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

from nono_dev import nono, project_config, style


# -- argparse wiring ---------------------------------------------------------


def _invariants_help(_args):
    print()
    print(style.banner("  nono-dev invariants"))
    print()
    print(style.help_row("invariants init", "[path] [--force]", "Create a starter invariants file for this repo"))
    print(style.help_row("invariants draft", "", "Spawn a sandboxed agent to draft a real invariants file"))
    print(style.help_row("invariants validate", "[path]", "Validate an invariants file against the schema"))
    print()
    sys.exit(0)


def add_parser(subparsers):
    inv_parser = subparsers.add_parser("invariants", help="Manage the invariants.yaml file")
    inv_sub = inv_parser.add_subparsers(dest="invariants_command")
    inv_parser.set_defaults(func=_invariants_help)

    # init
    init_parser = inv_sub.add_parser(
        "init",
        help="Create a starter invariants file for this repo",
    )
    init_parser.add_argument(
        "path", nargs="?", default=None,
        help="Path to write (default: docs/invariants.yaml)",
    )
    init_parser.add_argument(
        "--force", action="store_true",
        help="Overwrite an existing file",
    )
    init_parser.set_defaults(func=run_init)

    # draft
    draft_parser = inv_sub.add_parser(
        "draft",
        help="Spawn a sandboxed agent that drafts a real invariants file using nd graph",
    )
    draft_parser.add_argument(
        "--no-rollback", action="store_true",
        help="Disable rollback snapshots for this session",
    )
    nono.add_sandbox_pass_through_args(draft_parser)
    draft_parser.set_defaults(func=run_draft)

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


# -- init: write a starter template ------------------------------------------
#
# The template inherits the structural shape of a real invariants file
# (header prose, themed section dividers, multiple entries) so users learn
# the convention from the first entry, not after several rounds of review.
# Every example entry validates green out of the box. The `example-` id
# prefix and the inline call-to-action make it obvious they're placeholders.
#
# YAML-only on purpose: the inline comments and section dividers are doing
# real work, and JSON loses all of that. Users who want JSON can convert
# the result.

_TEMPLATE_YAML = """\
# Load-bearing invariants for this codebase.
#
# Purpose
# -------
# Each entry below is a rule that should not be broken without a conscious
# decision and a paper trail. The triage / review / fix workflows join these
# against the subsystems affected by an issue or PR and cite the relevant
# invariants so reviewers and agents both work from the same checklist.
#
# Schema (validated by `nd invariants validate`)
# ----------------------------------------------
# - id          slug, stable across runs. Reference in review comments.
# - subsystems  plain-English tags. Use generously -- a contributor describing
#                an issue may use any of several names for the same area.
# - statement   one sentence (or short paragraph). Must be actionable.
# - source      link to a doc + anchor, or a GitHub URL. Never leave empty.
# - severity    high   -- breaking it creates a security hole or correctness bug
#                medium -- violates API contract, testing discipline, or
#                          platform-specific behaviour
#                low    -- style / ergonomics / process
#
# When you add an invariant
# -------------------------
# - If it's a *decision* (why we did it this way), link to a design doc.
# - If it's a *rule* (don't do X), link to CLAUDE.md, an architecture doc,
#   or an issue that motivated it.
# - Keep statements concrete. "Handle errors well" is not an invariant;
#   "Return Result; library code must not .unwrap() or .expect()" is.
#
# When you break an invariant
# ---------------------------
# - It should require a conscious decision with a comment citing the id
#   (e.g. `// invariant <id>: intentionally deferred, see #NNN`).
#
# Replace the example entries below with rules that actually apply here,
# then run `nd invariants validate` to check.

# ---------------------------------------------------------------------------
# Structural
# ---------------------------------------------------------------------------

- id: example-no-unwrap-on-fallible-values
  subsystems: [core, error-handling]
  statement: >-
    Library code must not call .unwrap() or .expect() on values originating
    from user input, IO, or any fallible source. Propagate errors via
    Result; reserve panics for genuinely unreachable conditions.
  source: CLAUDE.md#error-handling
  severity: high
  added: {today}
  tags: [error-handling, robustness]

- id: example-no-shell-injection
  subsystems: [cli, security]
  statement: >-
    User-supplied strings must never be interpolated into shell command
    lines. Always pass arguments as a list to the subprocess API, never
    via shell=True or string concatenation.
  source: CLAUDE.md#security
  severity: high
  related: [example-no-unwrap-on-fallible-values]

# ---------------------------------------------------------------------------
# Coding standards
# ---------------------------------------------------------------------------

- id: example-no-dead-code-allow
  subsystems: [code-quality, testing]
  statement: >-
    Avoid #[allow(dead_code)] or equivalent suppressions. If code is unused,
    either remove it or add tests that exercise it. Dead code accumulates
    silently and hides real gaps in coverage.
  source: CLAUDE.md#coding-standards
  severity: low

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

# (Add testing-discipline invariants here.)

# ---------------------------------------------------------------------------
# Process
# ---------------------------------------------------------------------------

# (Add process / CI / commit-policy invariants here.)
"""


def run_init(args):
    """Write a starter invariants.yaml at the requested path."""
    target = args.path or "docs/invariants.yaml"

    # YAML-only: see comment above _TEMPLATE_YAML.
    ext = os.path.splitext(target)[1].lower()
    if ext not in (".yaml", ".yml"):
        print(
            style.error(
                f"`init` only writes YAML; got {target!r}. "
                "Use a .yaml extension or omit the path."
            ),
            file=sys.stderr,
        )
        sys.exit(2)

    if os.path.exists(target) and not args.force:
        print(
            style.error(
                f"{target} already exists. Pass --force to overwrite, "
                "or run `nd invariants validate` to check the existing file."
            ),
            file=sys.stderr,
        )
        sys.exit(2)

    parent = os.path.dirname(target)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)

    content = _TEMPLATE_YAML.format(today=date.today().isoformat())
    try:
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as exc:
        print(style.error(f"could not write {target}: {exc}"), file=sys.stderr)
        sys.exit(2)

    print(style.success(f"Wrote {target}"))
    print(
        f"  {style.label('next:')} edit the example entries, then run "
        f"{style.value('nd invariants validate')}"
    )


# -- draft: launch a sandboxed agent to bootstrap a real invariants file ----
#
# This is the headless launcher for the invariants-init skill. The skill
# itself lives at skills/invariants-init/SKILL.md (for slash-command
# discovery) and is mirrored into nono_dev/prompts/invariants_draft.md so
# the package ships it as a system prompt. Both copies are kept in sync.


def _draft_session_name(config):
    """Build a session name unique to the current repo.

    Uses the repo slug from config (last path segment of "org/repo") so
    drafts in different repos don't collide. Falls back to a generic name
    when the repo can't be inferred.
    """
    repo = project_config.get_repo(config) or ""
    slug = repo.split("/", 1)[1] if "/" in repo else (repo or "repo")
    # _slugify-equivalent: keep the result safe for session names.
    slug = re.sub(r"[^a-z0-9._-]+", "-", slug.lower()).strip("._-") or "repo"
    return f"invariants-draft-{slug}"


def run_draft(args):
    """Spawn a sandboxed Claude session loaded with the invariants-init skill."""
    nono.check_installed()
    config = project_config.load()
    project_root = project_config.get_project_root(config)

    graph_line = project_config.graph_path_for_prompt(config, repo_hint=project_root)
    staleness = project_config.graph_staleness_warning(config, repo_hint=project_root)
    if staleness:
        print(style.warning(staleness), file=sys.stderr)

    prompt_path = project_config.get_rendered_prompt_path(
        "invariants_draft", config, substitutions={"graph_path": graph_line},
    )

    rollback = project_config.get_rollback(config)
    if args.no_rollback:
        rollback["enabled"] = False

    workdir = os.getcwd()
    git_dir = os.path.join(project_root, ".git")
    session_name = _draft_session_name(config)

    # Refuse to launch a duplicate; surface attach instructions for the
    # existing session instead.
    sessions = nono.ps_json(include_all=False)
    for s in sessions:
        if s.get("name") == session_name:
            print(style.warning(f"Session '{session_name}' is already running."))
            print(
                f"  {style.label('Attach:')} "
                f"{style.value('nono-dev sb attach ' + s.get('session_id', session_name))}"
            )
            return

    extra_allows, extra_reads = nono.normalize_sandbox_paths(args)
    session_id = nono.run_detached(
        session_name,
        # The skill writes to proj/invariants.yaml under the project root,
        # so project_root needs write access; .git for any commits the
        # agent decides to make if the user asks.
        allows=[project_root, git_dir] + extra_allows,
        reads=extra_reads,
        allow_cwd=True,
        system_prompt=prompt_path,
        rollback=rollback,
        workdir=workdir,
    )

    print(style.success("Invariants draft session started"))
    print(f"  {style.label('Workspace:')} {style.value(workdir)}")
    print(f"  {style.label('Session:')}   {style.value(session_id)}")
    print(f"  {style.label('Attach:')}    {style.value('nono-dev sb attach ' + session_name)}")
