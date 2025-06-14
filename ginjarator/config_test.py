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


def test_minimal_parse_error() -> None:
    with pytest.raises(ValueError, match="templates"):
        config.Minimal.parse(dict(templates=[]))


def test_config_parse_error() -> None:
    with pytest.raises(ValueError, match="kumquat"):
        config.Config.parse(dict(kumquat="foo"))


@pytest.mark.parametrize(
    "config_raw,expected_config,expected_minimal_raw,expected_minimal",
    (
        (
            {},
            config.Config(
                source_paths=(pathlib.Path("src"),),
                build_paths=(pathlib.Path("build"),),
                ninja_templates=(),
                templates=(),
            ),
            dict(
                source_paths=["src"],
                build_paths=["build"],
            ),
            config.Minimal(
                source_paths=(pathlib.Path("src"),),
                build_paths=(pathlib.Path("build"),),
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
            dict(
                source_paths=["src1", "src2"],
                build_paths=["build1", "build2"],
            ),
            config.Minimal(
                source_paths=(pathlib.Path("src1"), pathlib.Path("src2")),
                build_paths=(pathlib.Path("build1"), pathlib.Path("build2")),
            ),
        ),
        (
            # Minimal's fields are normalized.
            dict(
                source_paths=["src2", "src2", "src1"],
                build_paths=["build2", "build2", "build1"],
            ),
            config.Config(
                source_paths=(pathlib.Path("src1"), pathlib.Path("src2")),
                build_paths=(pathlib.Path("build1"), pathlib.Path("build2")),
                ninja_templates=(),
                templates=(),
            ),
            dict(
                source_paths=["src1", "src2"],
                build_paths=["build1", "build2"],
            ),
            config.Minimal(
                source_paths=(pathlib.Path("src1"), pathlib.Path("src2")),
                build_paths=(pathlib.Path("build1"), pathlib.Path("build2")),
            ),
        ),
    ),
)
def test_config(
    config_raw: Any,
    expected_config: config.Config,
    expected_minimal_raw: Any,
    expected_minimal: config.Minimal,
) -> None:
    actual_config = config.Config.parse(config_raw)
    actual_minimal_raw = actual_config.serialize_minimal()
    actual_minimal = config.Minimal.parse(actual_minimal_raw)

    assert actual_config == expected_config
    assert actual_minimal_raw == expected_minimal_raw
    assert actual_minimal == expected_minimal
