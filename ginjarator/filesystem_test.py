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

from collections.abc import Callable
import json
import pathlib
import textwrap
import time

import pytest

from ginjarator import config
from ginjarator import filesystem
from ginjarator import paths


def _sleep_for_mtime() -> None:
    """Prevents writes before/after calling this from having the same mtime."""
    time.sleep(0.01)


@pytest.fixture(name="root_path")
def _root_path(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            source_paths = ["src"]
            build_paths = ["build"]
            """
        )
    )
    (tmp_path / ".ginjarator").mkdir()
    (tmp_path / ".ginjarator/config").mkdir()
    (tmp_path / ".ginjarator/config/minimal.json").write_text(
        json.dumps(
            dict(
                source_paths=["src"],
                build_paths=["build"],
            )
        )
    )
    return tmp_path


def test_mode_configure_twice() -> None:
    mode = filesystem.InternalMode()
    minimal_config = config.Minimal(source_paths=(), build_paths=())
    mode.configure(minimal_config=minimal_config, resolve=pathlib.Path)

    with pytest.raises(ValueError, match="Already configured"):
        mode.configure(minimal_config=minimal_config, resolve=pathlib.Path)


def test_mode_no_configure() -> None:
    with pytest.raises(ValueError, match="Not configured"):
        filesystem.InternalMode().minimal_config  # pylint: disable=expression-not-assigned
    with pytest.raises(ValueError, match="Not configured"):
        filesystem.InternalMode().resolve("")


@pytest.mark.parametrize(
    "mode,config_path",
    (
        (lambda _: filesystem.InternalMode(), paths.CONFIG),
        (lambda _: filesystem.NinjaMode(), paths.CONFIG),
        (lambda _: filesystem.ScanMode(), paths.MINIMAL_CONFIG),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(root / paths.MINIMAL_CONFIG,),
            ),
            paths.MINIMAL_CONFIG,
        ),
    ),
)
def test_init_depends_on_config(
    mode: Callable[[pathlib.Path], filesystem.Mode],
    config_path: pathlib.Path,
    root_path: pathlib.Path,
) -> None:
    fs = filesystem.Filesystem(root_path, mode=mode(root_path))
    assert set(fs.dependencies) == {root_path / config_path}


def test_filesystem_resolve(root_path: pathlib.Path) -> None:
    fs = filesystem.Filesystem(root_path)
    assert fs.resolve("foo") == root_path / "foo"


@pytest.mark.parametrize(
    "mode,path",
    (
        (lambda _: filesystem.InternalMode(), "relative"),
        (lambda _: filesystem.InternalMode(), "/absolute"),
        (lambda _: filesystem.NinjaMode(), "relative"),
        (lambda _: filesystem.NinjaMode(), "/absolute"),
        (lambda _: filesystem.NinjaMode(), "build/some-file"),
        (lambda _: filesystem.ScanMode(), "relative"),
        (lambda _: filesystem.ScanMode(), "/absolute"),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(
                    root / paths.MINIMAL_CONFIG,
                    root / "relative",
                ),
            ),
            "relative",
        ),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(
                    root / paths.MINIMAL_CONFIG,
                    pathlib.Path("/absolute"),
                ),
            ),
            "/absolute",
        ),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(root / paths.MINIMAL_CONFIG,),
            ),
            "src/some-file",
        ),
    ),
)
def test_filesystem_add_dependency_not_allowed(
    mode: Callable[[pathlib.Path], filesystem.Mode],
    path: str,
    root_path: pathlib.Path,
) -> None:
    fs = filesystem.Filesystem(root_path, mode=mode(root_path))

    with pytest.raises(ValueError, match="not in allowed paths"):
        fs.add_dependency(path)


@pytest.mark.parametrize(
    "mode,path",
    (
        (lambda _: filesystem.InternalMode(), "src/some-file"),
        (lambda _: filesystem.NinjaMode(), "src/some-file"),
        (lambda _: filesystem.ScanMode(), "src/some-file"),
        (lambda _: filesystem.ScanMode(), "build/some-file"),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(
                    root / paths.MINIMAL_CONFIG,
                    root / "src/some-file",
                ),
            ),
            "src/some-file",
        ),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(
                    root / paths.MINIMAL_CONFIG,
                    root / "build/some-file",
                ),
            ),
            "build/some-file",
        ),
    ),
)
def test_filesystem_add_dependency(
    mode: Callable[[pathlib.Path], filesystem.Mode],
    path: str,
    root_path: pathlib.Path,
) -> None:
    fs = filesystem.Filesystem(root_path, mode=mode(root_path))

    fs.add_dependency(path)

    assert set(fs.dependencies) >= {root_path / path}


@pytest.mark.parametrize(
    "mode,path",
    (
        (lambda _: filesystem.InternalMode(), "relative"),
        (lambda _: filesystem.InternalMode(), "/absolute"),
        (lambda _: filesystem.NinjaMode(), "relative"),
        (lambda _: filesystem.NinjaMode(), "/absolute"),
        (lambda _: filesystem.NinjaMode(), "build/some-file"),
        (lambda _: filesystem.ScanMode(), "relative"),
        (lambda _: filesystem.ScanMode(), "/absolute"),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(
                    root / paths.MINIMAL_CONFIG,
                    root / "relative",
                ),
            ),
            "relative",
        ),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(
                    root / paths.MINIMAL_CONFIG,
                    pathlib.Path("/absolute"),
                ),
            ),
            "/absolute",
        ),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(root / paths.MINIMAL_CONFIG,),
            ),
            "src/some-file",
        ),
    ),
)
@pytest.mark.parametrize("defer_ok", (False, True))
def test_filesystem_read_text_not_allowed(
    mode: Callable[[pathlib.Path], filesystem.Mode],
    path: str,
    defer_ok: bool,
    root_path: pathlib.Path,
) -> None:
    fs = filesystem.Filesystem(root_path, mode=mode(root_path))

    with pytest.raises(ValueError, match="not in allowed paths"):
        fs.read_text(path, defer_ok=defer_ok)


def test_filesystem_read_text_no_defer_exception(
    root_path: pathlib.Path,
) -> None:
    fs = filesystem.Filesystem(root_path, mode=filesystem.ScanMode())

    with pytest.raises(ValueError, match="deferring .* disabled"):
        fs.read_text("build/some-file", defer_ok=False)


def test_filesystem_read_text_returns_none(root_path: pathlib.Path) -> None:
    fs = filesystem.Filesystem(root_path, mode=filesystem.ScanMode())
    path = "build/not-built-yet"
    full_path = root_path / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text("stale contents from previous build")

    assert fs.read_text(path, defer_ok=True) is None
    assert set(fs.dependencies) >= {full_path}


@pytest.mark.parametrize(
    "mode,path",
    (
        (lambda _: filesystem.InternalMode(), "src/some-file"),
        (lambda _: filesystem.NinjaMode(), "src/some-file"),
        (lambda _: filesystem.ScanMode(), "src/some-file"),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(
                    root / paths.MINIMAL_CONFIG,
                    root / "src/some-file",
                ),
            ),
            "src/some-file",
        ),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(
                    root / paths.MINIMAL_CONFIG,
                    root / "build/some-file",
                ),
            ),
            "build/some-file",
        ),
    ),
)
@pytest.mark.parametrize("defer_ok", (False, True))
def test_filesystem_read_text_returns_contents(
    mode: Callable[[pathlib.Path], filesystem.Mode],
    path: str,
    defer_ok: bool,
    root_path: pathlib.Path,
) -> None:
    fs = filesystem.Filesystem(root_path, mode=mode(root_path))
    contents = "the contents of the file"
    full_path = root_path / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(contents)

    assert fs.read_text(path, defer_ok=defer_ok) == contents
    assert set(fs.dependencies) >= {full_path}


def test_filesystem_read_config(root_path: pathlib.Path) -> None:
    (root_path / "ginjarator.toml").write_text("source_paths = ['foo']")
    fs = filesystem.Filesystem(root_path)

    assert tuple(fs.read_config().source_paths) == (pathlib.Path("foo"),)
    assert set(fs.dependencies) >= {root_path / "ginjarator.toml"}


@pytest.mark.parametrize(
    "mode,path",
    (
        (lambda _: filesystem.InternalMode(), "relative"),
        (lambda _: filesystem.InternalMode(), "/absolute"),
        (lambda _: filesystem.InternalMode(), "src/some-file"),
        (lambda _: filesystem.InternalMode(), "build/some-file"),
        (lambda _: filesystem.NinjaMode(), "relative"),
        (lambda _: filesystem.NinjaMode(), "/absolute"),
        (lambda _: filesystem.NinjaMode(), "src/some-file"),
        (lambda _: filesystem.NinjaMode(), "build/some-file"),
        (lambda _: filesystem.ScanMode(), "relative"),
        (lambda _: filesystem.ScanMode(), "/absolute"),
        (lambda _: filesystem.ScanMode(), "src/some-file"),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(root / paths.MINIMAL_CONFIG,),
                outputs=(root / "relative",),
            ),
            "relative",
        ),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(root / paths.MINIMAL_CONFIG,),
                outputs=(pathlib.Path("/absolute"),),
            ),
            "/absolute",
        ),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(root / paths.MINIMAL_CONFIG,),
                outputs=(root / "src/some-file",),
            ),
            "src/some-file",
        ),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(root / paths.MINIMAL_CONFIG,),
            ),
            "build/some-file",
        ),
    ),
)
def test_filesystem_add_output_not_allowed(
    mode: Callable[[pathlib.Path], filesystem.Mode],
    path: str,
    root_path: pathlib.Path,
) -> None:
    fs = filesystem.Filesystem(root_path, mode=mode(root_path))

    with pytest.raises(ValueError, match="not in allowed paths"):
        fs.add_output(path)


@pytest.mark.parametrize(
    "mode,path",
    (
        (lambda _: filesystem.InternalMode(), ".ginjarator/some-file"),
        (lambda _: filesystem.ScanMode(), "build/some-file"),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(root / paths.MINIMAL_CONFIG,),
                outputs=(root / "build/some-file",),
            ),
            "build/some-file",
        ),
    ),
)
def test_filesystem_add_output(
    mode: Callable[[pathlib.Path], filesystem.Mode],
    path: str,
    root_path: pathlib.Path,
) -> None:
    fs = filesystem.Filesystem(root_path, mode=mode(root_path))

    fs.add_output(path)

    assert set(fs.outputs) == {root_path / path}


@pytest.mark.parametrize(
    "mode,path",
    (
        (lambda _: filesystem.InternalMode(), "relative"),
        (lambda _: filesystem.InternalMode(), "/absolute"),
        (lambda _: filesystem.InternalMode(), "src/some-file"),
        (lambda _: filesystem.InternalMode(), "build/some-file"),
        (lambda _: filesystem.NinjaMode(), "relative"),
        (lambda _: filesystem.NinjaMode(), "/absolute"),
        (lambda _: filesystem.NinjaMode(), "src/some-file"),
        (lambda _: filesystem.NinjaMode(), "build/some-file"),
        (lambda _: filesystem.ScanMode(), "relative"),
        (lambda _: filesystem.ScanMode(), "/absolute"),
        (lambda _: filesystem.ScanMode(), "src/some-file"),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(root / paths.MINIMAL_CONFIG,),
                outputs=(root / "relative",),
            ),
            "relative",
        ),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(root / paths.MINIMAL_CONFIG,),
                outputs=(pathlib.Path("/absolute"),),
            ),
            "/absolute",
        ),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(root / paths.MINIMAL_CONFIG,),
                outputs=(root / "src/some-file",),
            ),
            "src/some-file",
        ),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(root / paths.MINIMAL_CONFIG,),
            ),
            "build/some-file",
        ),
    ),
)
@pytest.mark.parametrize("defer_ok", (False, True))
def test_filesystem_write_text_not_allowed(
    mode: Callable[[pathlib.Path], filesystem.Mode],
    path: str,
    defer_ok: bool,
    root_path: pathlib.Path,
) -> None:
    fs = filesystem.Filesystem(root_path, mode=mode(root_path))

    with pytest.raises(ValueError, match="not in allowed paths"):
        fs.write_text(path, path, defer_ok=defer_ok)


def test_filesystem_write_text_no_defer_exception(
    root_path: pathlib.Path,
) -> None:
    fs = filesystem.Filesystem(root_path, mode=filesystem.ScanMode())

    with pytest.raises(ValueError, match="deferring .* disabled"):
        fs.write_text("build/some-file", "foo", defer_ok=False)


def test_filesystem_write_text_deferred(root_path: pathlib.Path) -> None:
    fs = filesystem.Filesystem(root_path, mode=filesystem.ScanMode())
    contents = "the contents of the file"
    path = "build/some-file"
    full_path = root_path / path

    changed = fs.write_text(path, contents, defer_ok=True)

    assert not full_path.exists()
    assert set(fs.outputs) == {full_path}
    assert not changed


@pytest.mark.parametrize(
    "mode,path",
    (
        (lambda _: filesystem.InternalMode(), ".ginjarator/some-file"),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(root / paths.MINIMAL_CONFIG,),
                outputs=(root / "build/some-file",),
            ),
            "build/some-file",
        ),
    ),
)
@pytest.mark.parametrize("defer_ok", (False, True))
def test_filesystem_write_text_noop(
    mode: Callable[[pathlib.Path], filesystem.Mode],
    path: str,
    defer_ok: bool,
    root_path: pathlib.Path,
) -> None:
    fs = filesystem.Filesystem(root_path, mode=mode(root_path))
    contents = "the contents of the file"
    full_path = root_path / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(contents)
    original_mtime = full_path.stat().st_mtime
    _sleep_for_mtime()

    changed = fs.write_text(
        path,
        contents,
        preserve_mtime=True,
        defer_ok=defer_ok,
    )

    assert full_path.read_text() == contents
    assert full_path.stat().st_mtime == original_mtime
    assert set(fs.outputs) == {full_path}
    assert not changed


@pytest.mark.parametrize(
    "mode,path",
    (
        (lambda _: filesystem.InternalMode(), ".ginjarator/some-file"),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(root / paths.MINIMAL_CONFIG,),
                outputs=(root / "build/some-file",),
            ),
            "build/some-file",
        ),
    ),
)
@pytest.mark.parametrize("defer_ok", (False, True))
def test_filesystem_write_text_writes_new_file(
    mode: Callable[[pathlib.Path], filesystem.Mode],
    path: str,
    defer_ok: bool,
    root_path: pathlib.Path,
) -> None:
    fs = filesystem.Filesystem(root_path, mode=mode(root_path))
    contents = "the contents of the file"
    full_path = root_path / path

    changed = fs.write_text(path, contents, defer_ok=defer_ok)

    assert full_path.read_text() == contents
    assert set(fs.outputs) == {full_path}
    assert changed


@pytest.mark.parametrize(
    "mode,path",
    (
        (lambda _: filesystem.InternalMode(), ".ginjarator/some-file"),
        (
            lambda root: filesystem.RenderMode(
                dependencies=(root / paths.MINIMAL_CONFIG,),
                outputs=(root / "build/some-file",),
            ),
            "build/some-file",
        ),
    ),
)
@pytest.mark.parametrize(
    "contents,preserve_mtime",
    (
        ("original contents of the file", False),
        ("new contents of the file", False),
        ("new contents of the file", True),
    ),
)
@pytest.mark.parametrize("defer_ok", (False, True))
def test_filesystem_write_text_updates_file(
    mode: Callable[[pathlib.Path], filesystem.Mode],
    path: str,
    contents: str,
    preserve_mtime: bool,
    defer_ok: bool,
    root_path: pathlib.Path,
) -> None:
    fs = filesystem.Filesystem(root_path, mode=mode(root_path))
    full_path = root_path / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text("original contents of the file")
    original_mtime = full_path.stat().st_mtime
    _sleep_for_mtime()

    changed = fs.write_text(
        path,
        contents,
        preserve_mtime=preserve_mtime,
        defer_ok=defer_ok,
    )

    assert full_path.read_text() == contents
    assert full_path.stat().st_mtime > original_mtime
    assert set(fs.outputs) == {full_path}
    assert changed


def test_filesystem_write_text_macro_deferred(root_path: pathlib.Path) -> None:
    fs = filesystem.Filesystem(root_path, mode=filesystem.ScanMode())
    contents = "the contents of the file"
    path = "build/some-file"
    full_path = root_path / path

    returned = fs.write_text_macro(path, caller=lambda: contents)

    assert not full_path.exists()
    assert returned == contents


def test_filesystem_write_text_macro_writes(root_path: pathlib.Path) -> None:
    fs = filesystem.Filesystem(
        root_path,
        mode=filesystem.RenderMode(
            dependencies=(root_path / paths.MINIMAL_CONFIG,),
            outputs=(root_path / "build/some-file",),
        ),
    )
    contents = "the contents of the file"
    path = "build/some-file"
    full_path = root_path / path

    returned = fs.write_text_macro(path, caller=lambda: contents)

    assert full_path.read_text() == contents
    assert returned == contents
