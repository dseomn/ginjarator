# Copyright 2025 David Mandelberg
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

import pathlib
import textwrap
from typing import Any
import urllib.parse
import xml.parsers.expat.model

import pytest

from ginjarator import _filesystem
from ginjarator import _paths
from ginjarator import _python

# NOTE: Since sys.path and sys.modules are global state, these tests must use
# unique module paths and names.


@pytest.fixture(name="api")
def _api(tmp_path: pathlib.Path) -> _python.Api:
    (tmp_path / "ginjarator.toml").write_text("")
    return _python.Api(fs=_filesystem.Filesystem(tmp_path))


def test_api_assert_no_message(api: _python.Api) -> None:
    with pytest.raises(AssertionError):
        api.assert_(False)


def test_api_assert_with_message(api: _python.Api) -> None:
    with pytest.raises(AssertionError, match="kumquat"):
        api.assert_(False, "kumquat")


@pytest.mark.parametrize(
    "args",
    (
        (),
        ("kumquat",),
    ),
)
def test_api_assert_noop(args: Any, api: _python.Api) -> None:
    api.assert_(True, *args)


def test_api_import(tmp_path: pathlib.Path) -> None:
    package = "ginjarator__python_test__test_api_import"
    (tmp_path / "ginjarator.toml").write_text("python_paths = ['src']")
    (tmp_path / "src").mkdir()
    package_path = tmp_path / "src" / package
    package_path.mkdir()
    (package_path / "__init__.py").write_text("")
    (package_path / "sub").mkdir()
    (package_path / "sub/__init__.py").write_text("")
    (package_path / "mod1.py").write_text(
        f"import {package}.mod2; mod2 = {package}.mod2"
    )
    (package_path / "mod2.py").write_text(f"import {package}.mod3 as mod3")
    (package_path / "mod3.py").write_text(f"from {package} import mod4")
    (package_path / "mod4.py").write_text(f"from {package} import mod5 as mod5")
    (package_path / "mod5.py").write_text("from .sub import mod6")
    (package_path / "sub/mod6.py").write_text("from .. import mod7")
    (package_path / "mod7.py").write_text(
        "from . import mod8; from .mod8 import not_a_module"
    )
    (package_path / "mod8.py").write_text("from .mod9 import *")
    (package_path / "mod9.py").write_text(
        textwrap.dedent(
            """
            import textwrap  # no dot
            import urllib.parse  # has dot
            import xml.parsers.expat.model  # __spec__ is None
            not_a_module = "kumquat"
            """
        )
    )
    fs = _filesystem.Filesystem(tmp_path)
    api = _python.Api(fs=fs)

    mod1 = api.import_(f"{package}.mod1")

    mod8 = mod1.mod2.mod3.mod4.mod5.mod6.mod7.mod8
    assert mod8.textwrap is textwrap
    assert mod8.urllib.parse is urllib.parse
    assert mod8.xml.parsers.expat.model is xml.parsers.expat.model
    assert fs.dependencies >= {
        _paths.Filesystem(f"src/{package}/__init__.py"),
        _paths.Filesystem(f"src/{package}/mod1.py"),
        _paths.Filesystem(f"src/{package}/mod2.py"),
        _paths.Filesystem(f"src/{package}/mod3.py"),
        _paths.Filesystem(f"src/{package}/mod4.py"),
        _paths.Filesystem(f"src/{package}/mod5.py"),
        _paths.Filesystem(f"src/{package}/sub/__init__.py"),
        _paths.Filesystem(f"src/{package}/sub/mod6.py"),
        _paths.Filesystem(f"src/{package}/mod7.py"),
        _paths.Filesystem(f"src/{package}/mod8.py"),
        _paths.Filesystem(f"src/{package}/mod9.py"),
    }


def test_api_import_import_top_level(tmp_path: pathlib.Path) -> None:
    name = "ginjarator__python_test__test_api_import_import_top_level"
    (tmp_path / "ginjarator.toml").write_text("python_paths = ['src']")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / f"{name}.py").write_text("foo = 'kumquat'")
    fs = _filesystem.Filesystem(tmp_path)
    api = _python.Api(fs=fs)

    module = api.import_(name)

    assert module.foo == "kumquat"
    assert fs.dependencies >= {_paths.Filesystem(f"src/{name}.py")}


def test_api_import_subsequent_import(tmp_path: pathlib.Path) -> None:
    """Tests that dependencies are tracked when the module is already cached."""
    package = "ginjarator__python_test__test_api_import_subsequent_import"
    (tmp_path / "ginjarator.toml").write_text("python_paths = ['src']")
    (tmp_path / "src").mkdir()
    package_path = tmp_path / "src" / package
    package_path.mkdir()
    (package_path / "__init__.py").write_text("")
    _python.Api(fs=_filesystem.Filesystem(tmp_path)).import_(package)
    fs = _filesystem.Filesystem(tmp_path)
    api = _python.Api(fs=fs)

    api.import_(package)

    assert fs.dependencies >= {_paths.Filesystem(f"src/{package}/__init__.py")}


def test_api_import_import_error(tmp_path: pathlib.Path) -> None:
    package = "ginjarator__python_test__test_api_import_import_error"
    (tmp_path / "ginjarator.toml").write_text("python_paths = ['src']")
    fs = _filesystem.Filesystem(tmp_path)
    api = _python.Api(fs=fs)

    with pytest.raises(ImportError):
        api.import_(package)


def test_api_raise_(api: _python.Api) -> None:
    with pytest.raises(_python.TemplateError, match="kumquat"):
        api.raise_("kumquat")
