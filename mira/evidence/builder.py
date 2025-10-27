"""Core evidence builder that orchestrates plugins."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .models import EvidenceCard, EvidencePack, EvidencePolicy, ManifestFile
from .plugins import default_plugins, infer_kind
from .plugins.base import EvidencePlugin

LOG = logging.getLogger(__name__)

EXCLUDED_DIR_NAMES = {".mira_cache", ".mira_evidence"}
EXCLUDED_FILE_NAMES = {
    "mira_feedback.yaml",
    "moodle_feedback.yaml",
    "moodle_comments.txt",
    "mira_evidence.json",
    "mira_evidence.txt",
    "grading_results.yaml",
    "grading_final.yaml",
}


def compute_hash(path: Path, policy: EvidencePolicy) -> str:
    """Stable cache key derived from file metadata and policy."""
    stat = path.stat()
    digest = hashlib.sha256()
    digest.update(str(path).encode("utf-8"))
    digest.update(str(stat.st_mtime_ns).encode("utf-8"))
    digest.update(str(stat.st_size).encode("utf-8"))
    digest.update(policy.hash_salt.encode("utf-8"))
    return digest.hexdigest()


class EvidenceBuilder:
    """Coordinator that runs registered plugins and enforces global limits."""

    def __init__(
        self,
        policy: Optional[EvidencePolicy] = None,
        cache_dir: Optional[Path] = None,
        plugins: Optional[Sequence[EvidencePlugin]] = None,
    ) -> None:
        self.policy = policy or EvidencePolicy()
        self.cache_dir = cache_dir
        self.plugins: List[EvidencePlugin] = list(plugins or default_plugins())
        self._cache_enabled = cache_dir is not None
        if self._cache_enabled and self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def build_manifest(self, submission_dir: Path) -> List[ManifestFile]:
        """
        Enumerate files that look relevant to grading.

        This is a deterministic scan (no LLM involvement) to keep the manifest
        small, focused, and reproducible.
        """
        candidates: List[ManifestFile] = []

        for path in submission_dir.rglob("*"):
            try:
                rel_path = path.relative_to(submission_dir)
            except ValueError:
                continue

            if any(part in EXCLUDED_DIR_NAMES for part in rel_path.parts):
                continue

            if path.is_dir():
                continue

            if path.name.startswith("."):
                continue

            if rel_path.name in EXCLUDED_FILE_NAMES:
                continue

            suffix = path.suffix or ""
            suffix_lower = suffix.lower()

            kind = infer_kind(rel_path, suffix_lower)
            if kind is None:
                continue

            try:
                stat = path.stat()
            except OSError as exc:
                LOG.warning("Skipping %s: %s", rel_path, exc)
                continue

            candidates.append(
                ManifestFile(
                    path=rel_path,
                    size=stat.st_size,
                    suffix=suffix_lower,
                    kind=kind,
                )
            )

        candidates.sort(key=lambda entry: entry.path.as_posix())
        if len(candidates) > self.policy.max_files:
            LOG.info(
                "Manifest truncated from %d to %d files per policy",
                len(candidates),
                self.policy.max_files,
            )
            candidates = candidates[: self.policy.max_files]
        return candidates

    def build_evidence(self, submission_dir: Path) -> EvidencePack:
        submission_dir = submission_dir.resolve()
        manifest = self.build_manifest(submission_dir)

        cards: List[EvidenceCard] = []
        running_bytes = 0

        for entry in manifest:
            plugin = self._find_plugin(entry)
            if not plugin:
                LOG.debug("No plugin for %s (%s)", entry.path, entry.kind)
                continue

            path_on_disk = submission_dir / entry.path
            card = self._get_cached_or_build(plugin, submission_dir, path_on_disk, entry)
            if not card:
                continue

            encoded = json.dumps(card.to_dict()).encode("utf-8", errors="ignore")
            candidate_total = running_bytes + len(encoded)
            if candidate_total > self.policy.max_total_bytes:
                LOG.info(
                    "Skipping %s; evidence budget reached (%d > %d bytes)",
                    entry.path,
                    candidate_total,
                    self.policy.max_total_bytes,
                )
                continue

            cards.append(card)
            running_bytes = candidate_total

        return EvidencePack(manifest=manifest, cards=cards, policy=self.policy)

    def _find_plugin(self, entry: ManifestFile) -> Optional[EvidencePlugin]:
        for plugin in self.plugins:
            if plugin.matches(entry):
                return plugin
        return None

    def _get_cached_or_build(
        self,
        plugin: EvidencePlugin,
        submission_root: Path,
        absolute_path: Path,
        manifest_entry: ManifestFile,
    ) -> Optional[EvidenceCard]:
        if not self._cache_enabled or self.cache_dir is None:
            return plugin.build(submission_root, manifest_entry, self.policy)

        cache_key = compute_hash(absolute_path, self.policy)
        cache_path = self.cache_dir / f"{cache_key}.json"

        if cache_path.exists():
            try:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                return EvidenceCard(
                    manifest_entry=manifest_entry,
                    summary=data["summary"],
                    snippets=list(data.get("snippets", [])),
                    stats=data.get("stats"),
                )
            except Exception as exc:
                LOG.warning("Failed to load cache for %s: %s", absolute_path, exc)
                cache_path.unlink(missing_ok=True)

        card = plugin.build(submission_root, manifest_entry, self.policy)
        if card and self._cache_enabled:
            cache_path.write_text(
                json.dumps(card.to_dict(), ensure_ascii=True, indent=2),
                encoding="utf-8",
            )
        return card
