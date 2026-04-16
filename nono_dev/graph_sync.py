"""Cache-sync extension point for graphify semantic caches.

Defines a pluggable interface for sharing graphify's per-file content-hashed
cache across developers. No backends ship initially -- `load_from_config`
always returns None. Adding an S3/git/HTTP backend later is additive.

Wiring: `nd graph build` / `nd graph update` call `pull()` before extraction
and `push()` after, wrapped in try/except that downgrades failures to warnings.
"""

from pathlib import Path
from typing import Protocol


class CacheSync(Protocol):
    def pull(self, cache_dir: Path) -> None:
        """Fetch any remote cache entries into cache_dir. No-op on first use."""

    def push(self, cache_dir: Path) -> None:
        """Upload any local cache entries that aren't already remote."""


def load_from_config(config: dict) -> CacheSync | None:
    """Return a sync backend from [graphs.cache_sync], or None.

    The config shape is reserved now so adding a backend later is additive.
    No backends are implemented yet.
    """
    _ = config.get("graphs", {}).get("cache_sync", {})
    return None
