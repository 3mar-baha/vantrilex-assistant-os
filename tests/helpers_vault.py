"""Shared GitHub API double for vault tests: real HTTP semantics, in-memory state.

Sprint-3 §3.1: VaultClient runs over httpx.MockTransport against this fake — status
codes, base64 payloads, sha bookkeeping and the Git Data API behave like the real
service, so the client's transport assumptions are exercised; only the network edge
is faked (test-guard rule 2: HTTP is a system boundary).
"""

from __future__ import annotations

import base64
import itertools
import json
from urllib.parse import unquote

import httpx


class FakeGitHub:
    def __init__(self, repo: str = "owner/vault-repo", branch: str = "main") -> None:
        self.repo = repo
        self.branch = branch
        self.objects: dict[str, tuple[str, str]] = {}  # path -> (blob sha, text)
        self.blobs: dict[str, str] = {}  # blob sha -> text (Git Data API)
        self.puts: list[dict] = []  # every Contents-API PUT body, recorded
        self.commits: list[dict] = []  # Data-API commits: {sha, message}
        self.requests: list[httpx.Request] = []
        self.fail_get_status: dict[str, int] = {}  # path -> forced GET status (401, ...)
        self.put_conflicts: dict[str, int] = {}  # path -> number of 409s to inject
        self.break_data_api = False  # True -> Git Data API endpoints return 500
        self._ids = itertools.count(1)
        self._head = "commit-0000-base"
        self._tree = "tree-0000-base"

    def seed(self, path: str, content: str) -> str:
        sha = f"blob-{next(self._ids):04d}"
        self.objects[path] = (sha, content)
        return sha

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _json(self, payload: object, status: int = 200) -> httpx.Response:
        return httpx.Response(status, json=payload)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        parts = unquote(request.url.path).removeprefix(f"/repos/{self.repo}/")
        method = request.method
        if method == "GET" and parts.startswith("contents/"):
            if request.url.params.get("ref") != self.branch:
                return self._json({"message": "ref required"}, status=422)
            return self._get_contents(parts.removeprefix("contents/"))
        if method == "PUT" and parts.startswith("contents/"):
            return self._put_contents(parts.removeprefix("contents/"), json.loads(request.content))
        if parts.startswith("git/") and self.break_data_api:
            return self._json({"message": "data api down"}, status=500)
        if method == "GET" and parts == f"git/ref/heads/{self.branch}":
            return self._json({"object": {"sha": self._head}})
        if method == "GET" and parts.startswith("git/commits/"):
            return self._json({"tree": {"sha": self._tree}})
        if method == "POST" and parts == "git/blobs":
            sha = f"blob-{next(self._ids):04d}"
            self.blobs[sha] = json.loads(request.content)["content"]
            return self._json({"sha": sha})
        if method == "POST" and parts == "git/trees":
            for entry in json.loads(request.content)["tree"]:
                if entry.get("sha") is None:
                    self.objects.pop(entry["path"], None)
                else:
                    self.objects[entry["path"]] = (entry["sha"], self.blobs[entry["sha"]])
            self._tree = f"tree-{next(self._ids):04d}"
            return self._json({"sha": self._tree})
        if method == "POST" and parts == "git/commits":
            body = json.loads(request.content)
            self._head = f"commit-{next(self._ids):04d}"
            self.commits.append({"sha": self._head, "message": body["message"]})
            return self._json({"sha": self._head})
        if method == "PATCH" and parts == f"git/refs/heads/{self.branch}":
            return self._json({"object": {"sha": self._head}})
        return self._json({"message": "Not Found"}, status=404)

    def _get_contents(self, path: str) -> httpx.Response:
        forced = self.fail_get_status.get(path)
        if forced is not None:
            return self._json({"message": "forced"}, status=forced)
        if path in self.objects:
            sha, content = self.objects[path]
            return self._json(
                {
                    "name": path.rsplit("/", 1)[-1],
                    "path": path,
                    "sha": sha,
                    "type": "file",
                    "encoding": "base64",
                    "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                }
            )
        prefix = path if path.endswith("/") else f"{path}/"
        children = [
            {"name": p.rsplit("/", 1)[-1], "path": p, "sha": sha, "type": "file"}
            for p, (sha, _) in self.objects.items()
            if p.startswith(prefix)
        ]
        if children:
            return self._json(children)
        return self._json({"message": "Not Found"}, status=404)

    def _put_contents(self, path: str, body: dict) -> httpx.Response:
        self.puts.append({"path": path, **body})
        if self.put_conflicts.get(path, 0) > 0:
            self.put_conflicts[path] -= 1
            return self._json({"message": "conflict"}, status=409)
        content = base64.b64decode(body["content"]).decode("utf-8")
        if path in self.objects:
            if body.get("sha") != self.objects[path][0]:
                return self._json({"message": "sha mismatch"}, status=409)
            created = False
        else:
            created = True
        new_sha = f"blob-{next(self._ids):04d}"
        self.objects[path] = (new_sha, content)
        commit_sha = f"commit-{next(self._ids):04d}"
        self._head = commit_sha
        return self._json(
            {"content": {"path": path, "sha": new_sha}, "commit": {"sha": commit_sha}},
            status=201 if created else 200,
        )
