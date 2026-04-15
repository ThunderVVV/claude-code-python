from __future__ import annotations

import asyncio

import cc_code.core.snapshot as snapshot_module
from cc_code.core.messages import Message, PatchContent, ToolUseContent
from cc_code.core.query_engine import QueryEngine
from cc_code.core.snapshot import DiffSummary, SnapshotManager
from cc_code.services.openai_client import OpenAIClientConfig


def _build_engine(working_directory: str) -> QueryEngine:
    config = OpenAIClientConfig(
        api_url="http://localhost",
        api_key="test",
        model_name="test-model",
        model_id="test-model",
    )
    return QueryEngine(
        client_config=config,
        tool_registry=object(),
        working_directory=working_directory,
        session_id="session-test",
    )


def _list_tree_files(manager: SnapshotManager, tree_hash: str) -> list[str]:
    result = manager._run_git(["ls-tree", "-r", "--name-only", tree_hash], check=True)
    return sorted([line for line in result.stdout.splitlines() if line.strip()])


def test_track_candidate_files_only_tracks_requested_paths(tmp_path, monkeypatch):
    snapshot_root = tmp_path / ".snapshot-store"
    monkeypatch.setattr(snapshot_module, "DEFAULT_SNAPSHOT_BASE_DIR", snapshot_root)

    working_dir = tmp_path / "repo"
    working_dir.mkdir()

    target = working_dir / "target.py"
    target.write_text("print('target')\n", encoding="utf-8")

    for i in range(200):
        (working_dir / f"other_{i}.py").write_text("print('other')\n", encoding="utf-8")

    manager = SnapshotManager(str(working_dir), project_id="test-project")
    tree_hash = manager.track(candidate_files=[str(target)])
    tracked_files = _list_tree_files(manager, tree_hash)

    assert tracked_files == ["target.py"]


def test_patch_candidate_files_detects_new_write_file(tmp_path, monkeypatch):
    snapshot_root = tmp_path / ".snapshot-store"
    monkeypatch.setattr(snapshot_module, "DEFAULT_SNAPSHOT_BASE_DIR", snapshot_root)

    working_dir = tmp_path / "repo"
    working_dir.mkdir()
    new_file = working_dir / "new_file.py"

    manager = SnapshotManager(str(working_dir), project_id="test-project")
    prev_hash = manager.track(candidate_files=[str(new_file)])

    new_file.write_text("print('created')\n", encoding="utf-8")
    patch = manager.patch(prev_hash, candidate_files=[str(new_file)])

    assert patch.prev_hash == prev_hash
    assert patch.files == [str(new_file)]


def test_query_engine_collects_file_modifying_paths():
    engine = _build_engine(".")
    tool_blocks = [
        ToolUseContent(id="1", name="Edit", input={"file_path": " /tmp/a.py "}),
        ToolUseContent(id="2", name="Read", input={"file_path": "/tmp/skip.py"}),
        ToolUseContent(id="3", name="Write", input={"file_path": "/tmp/b.py"}),
        ToolUseContent(id="4", name="Write", input={"file_path": "/tmp/b.py"}),
    ]

    assert engine._get_file_modifying_paths(tool_blocks) == ["/tmp/a.py", "/tmp/b.py"]


def test_revert_tracks_only_patch_files():
    class _FakeSnapshotManager:
        def __init__(self) -> None:
            self.track_calls: list[list[str]] = []
            self.diff_calls: list[tuple[str, str]] = []
            self.restore_calls: list[str] = []

        def track(self, candidate_files: list[str]) -> str:
            self.track_calls.append(candidate_files)
            return "snap-current"

        def diff(self, tree_hash1: str, tree_hash2: str) -> DiffSummary:
            self.diff_calls.append((tree_hash1, tree_hash2))
            return DiffSummary(additions=1, deletions=2, files=2, file_paths={"a", "b"})

        def restore(self, tree_hash: str) -> None:
            self.restore_calls.append(tree_hash)

    engine = _build_engine(".")
    manager = _FakeSnapshotManager()
    engine._snapshot_manager = manager

    user = Message.user_message("hello")
    assistant = Message.assistant_message(
        [PatchContent(prev_hash="prev-tree", hash="next-tree", files=["/tmp/a.py", "/tmp/b.py"])]
    )
    engine.state.messages = [user, assistant]

    result = asyncio.run(engine.revert())

    assert result.success is True
    assert manager.track_calls == [["/tmp/a.py", "/tmp/b.py"]]
    assert manager.diff_calls == [("prev-tree", "snap-current")]
    assert manager.restore_calls == ["prev-tree"]


def test_revert_without_patches_does_not_track():
    class _FakeSnapshotManager:
        def __init__(self) -> None:
            self.track_calls: list[list[str]] = []
            self.restore_calls: list[str] = []

        def track(self, candidate_files: list[str]) -> str:
            self.track_calls.append(candidate_files)
            return "unused"

        def diff(self, tree_hash1: str, tree_hash2: str) -> DiffSummary:
            return DiffSummary()

        def restore(self, tree_hash: str) -> None:
            self.restore_calls.append(tree_hash)

    engine = _build_engine(".")
    manager = _FakeSnapshotManager()
    engine._snapshot_manager = manager
    engine.state.messages = [Message.user_message("hello"), Message.assistant_message([])]

    result = asyncio.run(engine.revert())

    assert result.success is True
    assert manager.track_calls == []
    assert manager.restore_calls == []
