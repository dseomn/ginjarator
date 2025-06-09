# Copyright 2024 David Mandelberg
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=missing-module-docstring

from collections.abc import Generator
import contextlib
import pathlib
import re
import time

import pytest

from ginjarator import filesystem


def _sleep_for_mtime() -> None:
    """Prevents writes before/after calling this from having the same mtime."""
    time.sleep(0.01)


@pytest.fixture(name="exit_stack")
def _exit_stack() -> Generator[contextlib.ExitStack, None, None]:
    with contextlib.ExitStack() as stack:
        yield stack


@pytest.mark.parametrize(
    "config_contents,build_done_paths,error_regex",
    (
        (
            """
            source_paths = ["foo"]
            build_paths = ["foo"]
            """,
            [],
            r"must not overlap",
        ),
        (
            """
            source_paths = ["foo/bar"]
            build_paths = ["foo"]
            """,
            [],
            r"must not overlap",
        ),
        (
            """
            source_paths = ["foo"]
            build_paths = ["foo/bar"]
            """,
            [],
            r"must not overlap",
        ),
        (
            """
            source_paths = []
            build_paths = ["foo"]
            """,
            ["bar"],
            r"under build paths",
        ),
    ),
)
def test_filesystem_invalid_paths(
    config_contents: str,
    build_done_paths: list[str],
    error_regex: str,
    tmp_path: pathlib.Path,
) -> None:
    (tmp_path / filesystem.CONFIG_FILE).write_text(config_contents)
    with pytest.raises(ValueError, match=error_regex):
        filesystem.Filesystem(
            tmp_path,
            build_done_paths=tuple(map(pathlib.Path, build_done_paths)),
        )


def test_filesystem_exit_error(tmp_path: pathlib.Path) -> None:
    (tmp_path / "ginjarator.toml").write_text("")
    (tmp_path / "build").mkdir()
    (tmp_path / "build/unrelated").write_text("unrelated-contents")
    (tmp_path / "build/unmodified").write_text("unmodified-contents")
    (tmp_path / "build/modified").write_text("not-yet-modified-contents")

    with pytest.raises(ValueError, match="kumquat"):
        with filesystem.Filesystem(tmp_path) as fs:
            fs.write_text("build/unmodified", "unmodified-contents")
            fs.write_text("build/modified", "modified-contents")
            fs.write_text("build/new", "new-contents")
            raise ValueError("kumquat")

    assert {
        str(path.relative_to(tmp_path))
        for path in (tmp_path / "build").iterdir()
    } == {
        "build/unrelated",
        "build/unmodified",
        "build/modified",
        # Note that "build/new" is missing.
    }


def test_filesystem_exit_success(tmp_path: pathlib.Path) -> None:
    (tmp_path / "ginjarator.toml").write_text("")
    (tmp_path / "build").mkdir()
    (tmp_path / "build/unrelated").write_text("unrelated-contents")
    (tmp_path / "build/unmodified").write_text("unmodified-contents")
    (tmp_path / "build/modified").write_text("not-yet-modified-contents")

    with filesystem.Filesystem(tmp_path) as fs:
        fs.write_text("build/unmodified", "unmodified-contents")
        fs.write_text("build/modified", "modified-contents")
        fs.write_text("build/new", "new-contents")

    assert {
        str(path.relative_to(tmp_path))
        for path in (tmp_path / "build").iterdir()
    } == {
        "build/unrelated",
        "build/unmodified",
        "build/modified",
        "build/new",  # Not deleted.
    }


def test_filesystem_resolve(
    tmp_path: pathlib.Path,
    exit_stack: contextlib.ExitStack,
) -> None:
    (tmp_path / "ginjarator.toml").write_text("")
    fs = exit_stack.enter_context(filesystem.Filesystem(tmp_path))
    assert fs.resolve("foo") == tmp_path / "foo"


@pytest.mark.parametrize(
    "path",
    (
        "relative",
        "/absolute",
    ),
)
def test_filesystem_add_dependency_not_allowed(
    path: str,
    tmp_path: pathlib.Path,
    exit_stack: contextlib.ExitStack,
) -> None:
    (tmp_path / "ginjarator.toml").write_text("")
    fs = exit_stack.enter_context(filesystem.Filesystem(tmp_path))

    with pytest.raises(ValueError, match="not in allowed paths"):
        fs.add_dependency(path)


@pytest.mark.parametrize(
    "path",
    (
        "src/some-file",
        "build/some-file",
    ),
)
def test_filesystem_add_dependency(
    path: str,
    tmp_path: pathlib.Path,
    exit_stack: contextlib.ExitStack,
) -> None:
    (tmp_path / "ginjarator.toml").write_text("")
    fs = exit_stack.enter_context(filesystem.Filesystem(tmp_path))

    fs.add_dependency(path)

    assert set(fs.dependencies) == {tmp_path / path}


@pytest.mark.parametrize(
    "path",
    (
        "relative",
        "/absolute",
    ),
)
def test_filesystem_read_text_not_allowed(
    path: str,
    tmp_path: pathlib.Path,
    exit_stack: contextlib.ExitStack,
) -> None:
    (tmp_path / "ginjarator.toml").write_text("")
    fs = exit_stack.enter_context(filesystem.Filesystem(tmp_path))

    with pytest.raises(ValueError, match="not in allowed paths"):
        fs.read_text(path)


@pytest.mark.parametrize(
    "path",
    (
        "src/some-file",
        "build/already-built",
    ),
)
def test_filesystem_read_text_returns_contents(
    path: str,
    tmp_path: pathlib.Path,
    exit_stack: contextlib.ExitStack,
) -> None:
    (tmp_path / "ginjarator.toml").write_text("")
    fs = exit_stack.enter_context(
        filesystem.Filesystem(
            tmp_path,
            build_done_paths=(pathlib.Path("build/already-built"),),
        )
    )
    contents = "the contents of the file"
    full_path = tmp_path / path
    full_path.parent.mkdir(parents=True)
    full_path.write_text(contents)

    assert fs.read_text(path) == contents
    assert set(fs.dependencies) == {full_path}


def test_filesystem_read_text_returns_none(
    tmp_path: pathlib.Path,
    exit_stack: contextlib.ExitStack,
) -> None:
    (tmp_path / "ginjarator.toml").write_text("")
    fs = exit_stack.enter_context(filesystem.Filesystem(tmp_path))
    path = "build/not-built-yet"
    full_path = tmp_path / path
    full_path.parent.mkdir(parents=True)
    full_path.write_text("stale contents from previous build")

    assert fs.read_text(path) is None
    assert set(fs.dependencies) == {full_path}


@pytest.mark.parametrize(
    "path",
    (
        "relative",
        "/absolute",
        "src/some-file",
    ),
)
def test_filesystem_add_output_not_allowed(
    path: str,
    tmp_path: pathlib.Path,
    exit_stack: contextlib.ExitStack,
) -> None:
    (tmp_path / "ginjarator.toml").write_text("")
    fs = exit_stack.enter_context(filesystem.Filesystem(tmp_path))

    with pytest.raises(ValueError, match="not in allowed paths"):
        fs.add_output(path)


def test_filesystem_add_output(
    tmp_path: pathlib.Path,
    exit_stack: contextlib.ExitStack,
) -> None:
    (tmp_path / "ginjarator.toml").write_text("")
    fs = exit_stack.enter_context(filesystem.Filesystem(tmp_path))

    fs.add_output("build/some-file")

    assert set(fs.outputs) == {tmp_path / "build/some-file"}


@pytest.mark.parametrize(
    "path",
    (
        "relative",
        "/absolute",
        "src/some-file",
    ),
)
def test_filesystem_write_text_not_allowed(
    path: str,
    tmp_path: pathlib.Path,
    exit_stack: contextlib.ExitStack,
) -> None:
    (tmp_path / "ginjarator.toml").write_text("")
    fs = exit_stack.enter_context(filesystem.Filesystem(tmp_path))

    with pytest.raises(ValueError, match="not in allowed paths"):
        fs.write_text(path, "foo")


def test_filesystem_write_text_noop(
    tmp_path: pathlib.Path,
    exit_stack: contextlib.ExitStack,
) -> None:
    (tmp_path / "ginjarator.toml").write_text("")
    fs = exit_stack.enter_context(filesystem.Filesystem(tmp_path))
    contents = "the contents of the file"
    path = "build/some-file"
    full_path = tmp_path / path
    full_path.parent.mkdir(parents=True)
    full_path.write_text(contents)
    original_mtime = full_path.stat().st_mtime
    _sleep_for_mtime()

    fs.write_text(path, contents)

    assert full_path.read_text() == contents
    assert full_path.stat().st_mtime == original_mtime
    assert set(fs.outputs) == {full_path}


def test_filesystem_write_text_writes_new_file(
    tmp_path: pathlib.Path,
    exit_stack: contextlib.ExitStack,
) -> None:
    (tmp_path / "ginjarator.toml").write_text("")
    fs = exit_stack.enter_context(filesystem.Filesystem(tmp_path))
    contents = "the contents of the file"
    path = "build/some-file"
    full_path = tmp_path / path

    fs.write_text(path, contents)

    assert full_path.read_text() == contents
    assert set(fs.outputs) == {full_path}


def test_filesystem_write_text_updates_file(
    tmp_path: pathlib.Path,
    exit_stack: contextlib.ExitStack,
) -> None:
    (tmp_path / "ginjarator.toml").write_text("")
    fs = exit_stack.enter_context(filesystem.Filesystem(tmp_path))
    contents = "the contents of the file"
    path = "build/some-file"
    full_path = tmp_path / path
    full_path.parent.mkdir(parents=True)
    full_path.write_text("original contents of the file")
    original_mtime = full_path.stat().st_mtime
    _sleep_for_mtime()

    fs.write_text(path, contents)

    assert full_path.read_text() == contents
    assert full_path.stat().st_mtime > original_mtime
    assert set(fs.outputs) == {full_path}


def test_filesystem_write_text_macro(
    tmp_path: pathlib.Path,
    exit_stack: contextlib.ExitStack,
) -> None:
    (tmp_path / "ginjarator.toml").write_text("")
    fs = exit_stack.enter_context(filesystem.Filesystem(tmp_path))
    contents = "the contents of the file"
    path = "build/some-file"
    full_path = tmp_path / path

    returned = fs.write_text_macro(path, caller=lambda: contents)

    assert full_path.read_text() == contents
    assert returned == contents


def test_internal_path() -> None:
    assert re.fullmatch(
        r"\.ginjarator/dependencies/foo%2[Ff]bar\.json",
        str(filesystem.internal_path("dependencies", "foo/bar.json")),
    )


def test_template_state_path() -> None:
    assert filesystem.template_state_path("foo") == pathlib.Path(
        ".ginjarator/templates/foo.json"
    )
