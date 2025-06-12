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
from typing import Any

import pytest

from ginjarator import config


def test_config_parse_error() -> None:
    with pytest.raises(ValueError, match="kumquat"):
        config.Config.parse(dict(kumquat="foo"))


@pytest.mark.parametrize(
    "raw,expected",
    (
        (
            {},
            config.Config(
                source_paths=(pathlib.Path("src"),),
                build_paths=(pathlib.Path("build"),),
                ninja_templates=(),
                templates=(),
            ),
        ),
        (
            dict(
                source_paths=["src1", "src2"],
                build_paths=["build1", "build2"],
                ninja_templates=["n1.jinja", "n2.jinja"],
                templates=["t1.jinja", "t2.jinja"],
            ),
            config.Config(
                source_paths=(pathlib.Path("src1"), pathlib.Path("src2")),
                build_paths=(pathlib.Path("build1"), pathlib.Path("build2")),
                ninja_templates=(
                    pathlib.Path("n1.jinja"),
                    pathlib.Path("n2.jinja"),
                ),
                templates=(pathlib.Path("t1.jinja"), pathlib.Path("t2.jinja")),
            ),
        ),
    ),
)
def test_config_parse(raw: Any, expected: config.Config) -> None:
    assert config.Config.parse(raw) == expected
