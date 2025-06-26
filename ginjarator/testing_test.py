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

import pytest

import ginjarator
import ginjarator.testing


def test_api_for_scan(tmp_path: pathlib.Path) -> None:
    (tmp_path / "ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            templates = ["src/kumquat.jinja"]
            """
        )
    )

    with ginjarator.testing.api_for_scan(root_path=tmp_path):
        assert tuple(map(str, ginjarator.api().fs.read_config().templates)) == (
            "src/kumquat.jinja",
        )


def test_api_for_render_error() -> None:
    with pytest.raises(ValueError, match=r"write to a real project"):
        with ginjarator.testing.api_for_render(outputs=("build/out",)):
            pass


def test_api_for_render(tmp_path: pathlib.Path) -> None:
    (tmp_path / "ginjarator.toml").write_text(
        textwrap.dedent(
            """\
            build_paths = ["build"]
            """
        )
    )

    with ginjarator.testing.api_for_render(
        root_path=tmp_path,
        outputs=("build/out",),
    ):
        ginjarator.api().fs.write_text("build/out", "kumquat")

    assert (tmp_path / "build/out").read_text() == "kumquat"
