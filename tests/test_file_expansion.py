from __future__ import annotations

from pathlib import Path

import pytest

from cc_code.core.file_expansion import expand_file_references, expand_web


def test_expand_file_references_ignores_plain_text_without_web_marker(tmp_path):
    expanded_text, expansions = expand_file_references("你好", str(tmp_path))

    assert expanded_text == "你好"
    assert expansions == []


def test_expand_web_only_checks_skills_when_web_marker_present(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert expand_web("hello") == "hello"

    with pytest.raises(ValueError, match=r"@web requires skill\(s\)"):
        expand_web("@web explain this")
