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
import subprocess
import textwrap
from typing import Any

import pytest

from ginjarator import _build
from ginjarator import _paths


@pytest.mark.parametrize(
    "value,escape_shell,expected",
    (
        ("foo: $bar", True, "'foo$:$ $$bar'"),
        ("foo: $bar", False, "foo$:$ $$bar"),
        (_paths.Filesystem("foo"), False, "foo"),
        (["foo", "bar"], False, "foo bar"),
        (("foo", "bar"), False, "foo bar"),
        ({"foo", "bar"}, False, "bar foo"),
        (frozenset(("foo", "bar")), False, "bar foo"),
    ),
)
def test_to_ninja(value: Any, escape_shell: bool, expected: str) -> None:
    assert _build.to_ninja(value, escape_shell=escape_shell) == expected


@pytest.mark.parametrize(
    "value",
    (
        "not # a comment",
        "with\nnewline",
        object(),
    ),
)
def test_to_ninja_error(value: Any) -> None:
    with pytest.raises(NotImplementedError, match="Can't convert"):
        _build.to_ninja(value, escape_shell=False)


@pytest.mark.parametrize(
    "path",
    (
        "foo bar",
        "foo\x01bar",
        "foo:bar",
    ),
)
def test_to_depfile_error(path: str) -> None:
    with pytest.raises(NotImplementedError, match="Unsupported characters"):
        _build.to_depfile(first_output=path, dependencies=("foo",))


def test_to_depfile() -> None:
    assert _build.to_depfile(
        first_output="t1",
        dependencies=("d1", "d2"),
    ) == textwrap.dedent(
        """\
        t1: d1
        t1: d2
        """
    )


def test_to_depfile_ninja_requires_depfile_outputs_to_be_known(
    tmp_path: pathlib.Path,
) -> None:
    # This test isn't important to _build.py, but
    # test_to_depfile_escaping_works_with_ninja() below relies on this behavior
    # of ninja to test that the depfile outputs are escaped correctly.
    (tmp_path / "input").write_text("")
    (tmp_path / "depfile").write_text(
        "\n".join(
            (
                _build.to_depfile(
                    first_output="output",
                    dependencies=("input",),
                ),
                _build.to_depfile(
                    first_output="unknown-kumquat",
                    dependencies=("input",),
                ),
            )
        )
    )
    (tmp_path / "build.ninja").write_text(
        textwrap.dedent(
            """\
            rule copy
                command = cp -f $in $out
                depfile = depfile
            build output: copy input
            """
        )
    )

    result = subprocess.run(
        ("ninja", "-C", str(tmp_path), "-d", "explain"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )
    returncode = result.returncode
    assert returncode != 0, result.stdout
    assert "unknown-kumquat" in result.stdout


def test_to_depfile_escaping_works_with_ninja(tmp_path: pathlib.Path) -> None:
    filenames_to_test = ("foo%bar",)
    (tmp_path / "input").write_text("kumquat")
    (tmp_path / "depfile").write_text(
        "\n".join(
            (
                _build.to_depfile(
                    first_output="output",
                    dependencies=("input",),
                ),
                *(
                    _build.to_depfile(
                        first_output=filename,
                        dependencies=("input",),
                    )
                    for filename in filenames_to_test
                ),
            )
        )
    )
    (tmp_path / "build.ninja").write_text(
        textwrap.dedent(
            f"""\
            rule copy
                command = for f in $out; do cp -f $in "$$f" || exit $$?; done
                depfile = depfile
            build output {_build.to_ninja(filenames_to_test)}: copy input
            """
        )
    )

    result = subprocess.run(
        ("ninja", "-C", str(tmp_path), "-d", "explain"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )
    returncode = result.returncode
    assert returncode == 0, result.stdout
    for filename in filenames_to_test:
        assert (tmp_path / filename).read_text() == "kumquat"
