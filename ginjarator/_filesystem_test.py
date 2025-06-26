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

import copy
import json
import pathlib
import textwrap

import pytest

from ginjarator import _config
from ginjarator import _filesystem
from ginjarator import _paths


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
    mode = _filesystem.InternalMode()
    minimal_config = _config.Minimal(
        source_paths=(),
        build_paths=(),
        python_paths=(),
    )
    mode.configure(minimal_config=minimal_config)

    with pytest.raises(ValueError, match="Already configured"):
        mode.configure(minimal_config=minimal_config)


def test_mode_no_configure() -> None:
    with pytest.raises(ValueError, match="Not configured"):
        _filesystem.InternalMode().minimal_config  # pylint: disable=expression-not-assigned


@pytest.mark.parametrize(
    "mode,config_path",
    (
        (_filesystem.InternalMode(), _paths.CONFIG),
        (_filesystem.NinjaMode(), _paths.CONFIG),
        (_filesystem.ScanMode(), _paths.MINIMAL_CONFIG),
        (_filesystem.TestScanMode(), _paths.CONFIG),
        (
            _filesystem.RenderMode(dependencies=(_paths.MINIMAL_CONFIG,)),
            _paths.MINIMAL_CONFIG,
        ),
        (
            _filesystem.TestRenderMode(dependencies=(_paths.CONFIG,)),
            _paths.CONFIG,
        ),
    ),
)
def test_init_depends_on_config(
    mode: _filesystem.Mode,
    config_path: _paths.Filesystem,
    root_path: pathlib.Path,
) -> None:
    fs = _filesystem.Filesystem(root_path, mode=mode)
    assert set(fs.dependencies) == {config_path}


@pytest.mark.parametrize(
    "mode,path",
    (
        (_filesystem.InternalMode(), "relative"),
        (_filesystem.InternalMode(), "/absolute"),
        (_filesystem.NinjaMode(), "relative"),
        (_filesystem.NinjaMode(), "/absolute"),
        (_filesystem.NinjaMode(), "build/some-file"),
        (_filesystem.ScanMode(), "relative"),
        (_filesystem.ScanMode(), "/absolute"),
        (
            _filesystem.RenderMode(
                dependencies=(
                    _paths.MINIMAL_CONFIG,
                    _paths.Filesystem("relative"),
                ),
            ),
            "relative",
        ),
        (
            _filesystem.RenderMode(
                dependencies=(
                    _paths.MINIMAL_CONFIG,
                    _paths.Filesystem("/absolute"),
                ),
            ),
            "/absolute",
        ),
        (
            _filesystem.RenderMode(
                dependencies=(_paths.MINIMAL_CONFIG,),
            ),
            "src/some-file",
        ),
    ),
)
@pytest.mark.parametrize("defer_ok", (False, True))
def test_filesystem_add_dependency_not_allowed(
    mode: _filesystem.Mode,
    path: str,
    defer_ok: bool,
    root_path: pathlib.Path,
) -> None:
    fs = _filesystem.Filesystem(root_path, mode=copy.deepcopy(mode))

    with pytest.raises(ValueError, match="not in allowed paths"):
        fs.add_dependency(path, defer_ok=defer_ok)


@pytest.mark.parametrize(
    "mode,path",
    (
        (_filesystem.InternalMode(), "src/some-file"),
        (_filesystem.NinjaMode(), "src/some-file"),
        (_filesystem.ScanMode(), "src/some-file"),
        (
            _filesystem.RenderMode(
                dependencies=(
                    _paths.MINIMAL_CONFIG,
                    _paths.Filesystem("src/some-file"),
                ),
            ),
            "src/some-file",
        ),
        (
            _filesystem.RenderMode(
                dependencies=(
                    _paths.MINIMAL_CONFIG,
                    _paths.Filesystem("build/some-file"),
                ),
            ),
            "build/some-file",
        ),
    ),
)
@pytest.mark.parametrize("defer_ok", (False, True))
def test_filesystem_add_dependency_not_deferred(
    mode: _filesystem.Mode,
    path: str,
    root_path: pathlib.Path,
    defer_ok: bool,
) -> None:
    fs = _filesystem.Filesystem(root_path, mode=copy.deepcopy(mode))

    fs.add_dependency(path, defer_ok=defer_ok)

    assert set(fs.dependencies) >= {_paths.Filesystem(path)}


def test_filesystem_add_dependency_deferred(root_path: pathlib.Path) -> None:
    fs = _filesystem.Filesystem(root_path, mode=_filesystem.ScanMode())
    path = "build/some-file"

    fs.add_dependency(path, defer_ok=True)

    assert set(fs.deferred_dependencies) == {_paths.Filesystem(path)}


@pytest.mark.parametrize(
    "mode,path",
    (
        (_filesystem.InternalMode(), "relative"),
        (_filesystem.InternalMode(), "/absolute"),
        (_filesystem.NinjaMode(), "relative"),
        (_filesystem.NinjaMode(), "/absolute"),
        (_filesystem.NinjaMode(), "build/some-file"),
        (_filesystem.ScanMode(), "relative"),
        (_filesystem.ScanMode(), "/absolute"),
        (
            _filesystem.RenderMode(
                dependencies=(
                    _paths.MINIMAL_CONFIG,
                    _paths.Filesystem("relative"),
                ),
            ),
            "relative",
        ),
        (
            _filesystem.RenderMode(
                dependencies=(
                    _paths.MINIMAL_CONFIG,
                    _paths.Filesystem("/absolute"),
                ),
            ),
            "/absolute",
        ),
        (
            _filesystem.RenderMode(
                dependencies=(_paths.MINIMAL_CONFIG,),
            ),
            "src/some-file",
        ),
    ),
)
@pytest.mark.parametrize("defer_ok", (False, True))
def test_filesystem_read_text_not_allowed(
    mode: _filesystem.Mode,
    path: str,
    defer_ok: bool,
    root_path: pathlib.Path,
) -> None:
    fs = _filesystem.Filesystem(root_path, mode=copy.deepcopy(mode))

    with pytest.raises(ValueError, match="not in allowed paths"):
        fs.read_text(path, defer_ok=defer_ok)


def test_filesystem_read_text_no_defer_exception(
    root_path: pathlib.Path,
) -> None:
    fs = _filesystem.Filesystem(root_path, mode=_filesystem.ScanMode())

    with pytest.raises(ValueError, match="deferring .* disabled"):
        fs.read_text("build/some-file", defer_ok=False)


def test_filesystem_read_text_returns_none(root_path: pathlib.Path) -> None:
    fs = _filesystem.Filesystem(root_path, mode=_filesystem.ScanMode())
    path = "build/not-built-yet"
    full_path = root_path / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text("stale contents from previous build")

    assert fs.read_text(path, defer_ok=True) is None
    assert set(fs.deferred_dependencies) == {_paths.Filesystem(path)}


@pytest.mark.parametrize(
    "mode,path",
    (
        (_filesystem.InternalMode(), "src/some-file"),
        (_filesystem.NinjaMode(), "src/some-file"),
        (_filesystem.ScanMode(), "src/some-file"),
        (
            _filesystem.RenderMode(
                dependencies=(
                    _paths.MINIMAL_CONFIG,
                    _paths.Filesystem("src/some-file"),
                ),
            ),
            "src/some-file",
        ),
        (
            _filesystem.RenderMode(
                dependencies=(
                    _paths.MINIMAL_CONFIG,
                    _paths.Filesystem("build/some-file"),
                ),
            ),
            "build/some-file",
        ),
    ),
)
@pytest.mark.parametrize("defer_ok", (False, True))
def test_filesystem_read_text_returns_contents(
    mode: _filesystem.Mode,
    path: str,
    defer_ok: bool,
    root_path: pathlib.Path,
) -> None:
    fs = _filesystem.Filesystem(root_path, mode=copy.deepcopy(mode))
    contents = "the contents of the file"
    full_path = root_path / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(contents)

    assert fs.read_text(path, defer_ok=defer_ok) == contents
    assert set(fs.dependencies) >= {_paths.Filesystem(path)}


def test_filesystem_read_minimal_config(root_path: pathlib.Path) -> None:
    (root_path / "ginjarator.toml").write_text("source_paths = ['foo']")
    fs = _filesystem.Filesystem(root_path)

    minimal_config = fs.read_minimal_config()

    assert tuple(minimal_config.source_paths) == (_paths.Filesystem("foo"),)
    assert not isinstance(minimal_config, _config.Config)


def test_filesystem_read_config(root_path: pathlib.Path) -> None:
    (root_path / "ginjarator.toml").write_text("source_paths = ['foo']")
    fs = _filesystem.Filesystem(root_path)

    assert tuple(fs.read_config().source_paths) == (_paths.Filesystem("foo"),)
    assert set(fs.dependencies) >= {_paths.Filesystem("ginjarator.toml")}


@pytest.mark.parametrize(
    "mode,path",
    (
        (_filesystem.InternalMode(), "relative"),
        (_filesystem.InternalMode(), "/absolute"),
        (_filesystem.InternalMode(), "src/some-file"),
        (_filesystem.InternalMode(), "build/some-file"),
        (_filesystem.NinjaMode(), "relative"),
        (_filesystem.NinjaMode(), "/absolute"),
        (_filesystem.NinjaMode(), "src/some-file"),
        (_filesystem.NinjaMode(), "build/some-file"),
        (_filesystem.ScanMode(), "relative"),
        (_filesystem.ScanMode(), "/absolute"),
        (_filesystem.ScanMode(), "src/some-file"),
        (
            _filesystem.RenderMode(
                dependencies=(_paths.MINIMAL_CONFIG,),
                outputs=(_paths.Filesystem("relative"),),
            ),
            "relative",
        ),
        (
            _filesystem.RenderMode(
                dependencies=(_paths.MINIMAL_CONFIG,),
                outputs=(_paths.Filesystem("/absolute"),),
            ),
            "/absolute",
        ),
        (
            _filesystem.RenderMode(
                dependencies=(_paths.MINIMAL_CONFIG,),
                outputs=(_paths.Filesystem("src/some-file"),),
            ),
            "src/some-file",
        ),
        (
            _filesystem.RenderMode(
                dependencies=(_paths.MINIMAL_CONFIG,),
            ),
            "build/some-file",
        ),
    ),
)
@pytest.mark.parametrize("defer_ok", (False, True))
def test_filesystem_add_output_not_allowed(
    mode: _filesystem.Mode,
    path: str,
    defer_ok: bool,
    root_path: pathlib.Path,
) -> None:
    fs = _filesystem.Filesystem(root_path, mode=copy.deepcopy(mode))

    with pytest.raises(ValueError, match="not in allowed paths"):
        fs.add_output(path, defer_ok=defer_ok)


@pytest.mark.parametrize(
    "mode,path",
    (
        (_filesystem.InternalMode(), ".ginjarator/some-file"),
        (
            _filesystem.RenderMode(
                dependencies=(_paths.MINIMAL_CONFIG,),
                outputs=(_paths.Filesystem("build/some-file"),),
            ),
            "build/some-file",
        ),
    ),
)
@pytest.mark.parametrize("defer_ok", (False, True))
def test_filesystem_add_output_not_deferred(
    mode: _filesystem.Mode,
    path: str,
    defer_ok: bool,
    root_path: pathlib.Path,
) -> None:
    fs = _filesystem.Filesystem(root_path, mode=copy.deepcopy(mode))

    fs.add_output(path, defer_ok=defer_ok)

    assert set(fs.outputs) == {_paths.Filesystem(path)}


def test_filesystem_add_output_deferred(root_path: pathlib.Path) -> None:
    fs = _filesystem.Filesystem(root_path, mode=_filesystem.ScanMode())
    path = "build/some-file"

    fs.add_output(path, defer_ok=True)

    assert set(fs.deferred_outputs) == {_paths.Filesystem(path)}


@pytest.mark.parametrize(
    "mode,path",
    (
        (_filesystem.InternalMode(), "relative"),
        (_filesystem.InternalMode(), "/absolute"),
        (_filesystem.InternalMode(), "src/some-file"),
        (_filesystem.InternalMode(), "build/some-file"),
        (_filesystem.NinjaMode(), "relative"),
        (_filesystem.NinjaMode(), "/absolute"),
        (_filesystem.NinjaMode(), "src/some-file"),
        (_filesystem.NinjaMode(), "build/some-file"),
        (_filesystem.ScanMode(), "relative"),
        (_filesystem.ScanMode(), "/absolute"),
        (_filesystem.ScanMode(), "src/some-file"),
        (
            _filesystem.RenderMode(
                dependencies=(_paths.MINIMAL_CONFIG,),
                outputs=(_paths.Filesystem("relative"),),
            ),
            "relative",
        ),
        (
            _filesystem.RenderMode(
                dependencies=(_paths.MINIMAL_CONFIG,),
                outputs=(_paths.Filesystem("/absolute"),),
            ),
            "/absolute",
        ),
        (
            _filesystem.RenderMode(
                dependencies=(_paths.MINIMAL_CONFIG,),
                outputs=(_paths.Filesystem("src/some-file"),),
            ),
            "src/some-file",
        ),
        (
            _filesystem.RenderMode(
                dependencies=(_paths.MINIMAL_CONFIG,),
            ),
            "build/some-file",
        ),
    ),
)
@pytest.mark.parametrize("defer_ok", (False, True))
def test_filesystem_write_text_not_allowed(
    mode: _filesystem.Mode,
    path: str,
    defer_ok: bool,
    root_path: pathlib.Path,
) -> None:
    fs = _filesystem.Filesystem(root_path, mode=copy.deepcopy(mode))

    with pytest.raises(ValueError, match="not in allowed paths"):
        fs.write_text(path, path, defer_ok=defer_ok)


def test_filesystem_write_text_no_defer_exception(
    root_path: pathlib.Path,
) -> None:
    fs = _filesystem.Filesystem(root_path, mode=_filesystem.ScanMode())

    with pytest.raises(ValueError, match="deferring .* disabled"):
        fs.write_text("build/some-file", "foo", defer_ok=False)


def test_filesystem_write_text_deferred(root_path: pathlib.Path) -> None:
    fs = _filesystem.Filesystem(root_path, mode=_filesystem.ScanMode())
    contents = "the contents of the file"
    path = "build/some-file"
    full_path = root_path / path

    fs.write_text(path, contents, defer_ok=True)

    assert not full_path.exists()
    assert set(fs.deferred_outputs) == {_paths.Filesystem(path)}


@pytest.mark.parametrize(
    "mode,path",
    (
        (_filesystem.InternalMode(), ".ginjarator/some-file"),
        (
            _filesystem.RenderMode(
                dependencies=(_paths.MINIMAL_CONFIG,),
                outputs=(_paths.Filesystem("build/some-file"),),
            ),
            "build/some-file",
        ),
    ),
)
@pytest.mark.parametrize("defer_ok", (False, True))
def test_filesystem_write_text_writes_new_file(
    mode: _filesystem.Mode,
    path: str,
    defer_ok: bool,
    root_path: pathlib.Path,
) -> None:
    fs = _filesystem.Filesystem(root_path, mode=copy.deepcopy(mode))
    contents = "the contents of the file"
    full_path = root_path / path

    fs.write_text(path, contents, defer_ok=defer_ok)

    assert full_path.read_text() == contents
    assert set(fs.outputs) == {_paths.Filesystem(path)}


@pytest.mark.parametrize(
    "mode,path",
    (
        (_filesystem.InternalMode(), ".ginjarator/some-file"),
        (
            _filesystem.RenderMode(
                dependencies=(_paths.MINIMAL_CONFIG,),
                outputs=(_paths.Filesystem("build/some-file"),),
            ),
            "build/some-file",
        ),
    ),
)
@pytest.mark.parametrize("defer_ok", (False, True))
def test_filesystem_write_text_updates_file(
    mode: _filesystem.Mode,
    path: str,
    defer_ok: bool,
    root_path: pathlib.Path,
) -> None:
    fs = _filesystem.Filesystem(root_path, mode=copy.deepcopy(mode))
    full_path = root_path / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text("original contents of the file")

    fs.write_text(path, "new contents of the file", defer_ok=defer_ok)

    assert full_path.read_text() == "new contents of the file"
    assert set(fs.outputs) == {_paths.Filesystem(path)}


def test_filesystem_write_text_macro_deferred(root_path: pathlib.Path) -> None:
    fs = _filesystem.Filesystem(root_path, mode=_filesystem.ScanMode())
    contents = "the contents of the file"
    path = "build/some-file"
    full_path = root_path / path

    returned = fs.write_text_macro(path, caller=lambda: contents)

    assert not full_path.exists()
    assert returned == contents


def test_filesystem_write_text_macro_writes(root_path: pathlib.Path) -> None:
    fs = _filesystem.Filesystem(
        root_path,
        mode=_filesystem.RenderMode(
            dependencies=(_paths.MINIMAL_CONFIG,),
            outputs=(_paths.Filesystem("build/some-file"),),
        ),
    )
    contents = "the contents of the file"
    path = "build/some-file"
    full_path = root_path / path

    returned = fs.write_text_macro(path, caller=lambda: contents)

    assert full_path.read_text() == contents
    assert returned == contents
