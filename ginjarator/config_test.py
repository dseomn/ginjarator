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

from typing import Any

import pytest

from ginjarator import config
from ginjarator import paths


@pytest.mark.parametrize(
    "kwargs,error_regex",
    (
        (
            dict(
                source_paths=(paths.Filesystem("foo"),),
                build_paths=(paths.Filesystem("foo"),),
                python_paths=(),
            ),
            r"must not overlap",
        ),
        (
            dict(
                source_paths=(paths.Filesystem("foo/bar"),),
                build_paths=(paths.Filesystem("foo"),),
                python_paths=(),
            ),
            r"must not overlap",
        ),
        (
            dict(
                source_paths=(paths.Filesystem("foo"),),
                build_paths=(paths.Filesystem("foo/bar"),),
                python_paths=(),
            ),
            r"must not overlap",
        ),
        (
            dict(
                source_paths=(paths.Filesystem("foo/bar"),),
                build_paths=(),
                python_paths=(paths.Filesystem("foo"),),
            ),
            r"python_paths must all be within source_paths",
        ),
    ),
)
def test_minimal_error(kwargs: dict[str, Any], error_regex: str) -> None:
    with pytest.raises(ValueError, match=error_regex):
        config.Minimal(**kwargs)


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
                source_paths=(paths.Filesystem("src"),),
                build_paths=(paths.Filesystem("build"),),
                python_paths=(),
                ninja_templates=(),
                templates=(),
            ),
            dict(
                source_paths=["src"],
                build_paths=["build"],
                python_paths=[],
            ),
            config.Minimal(
                source_paths=(paths.Filesystem("src"),),
                build_paths=(paths.Filesystem("build"),),
                python_paths=(),
            ),
        ),
        (
            dict(
                source_paths=["src1", "src2"],
                build_paths=["build1", "build2"],
                python_paths=["src1/py", "src2/py"],
                ninja_templates=["n1.jinja", "n2.jinja"],
                templates=["t1.jinja", "t2.jinja"],
            ),
            config.Config(
                source_paths=(
                    paths.Filesystem("src1"),
                    paths.Filesystem("src2"),
                ),
                build_paths=(
                    paths.Filesystem("build1"),
                    paths.Filesystem("build2"),
                ),
                python_paths=(
                    paths.Filesystem("src1/py"),
                    paths.Filesystem("src2/py"),
                ),
                ninja_templates=(
                    paths.Filesystem("n1.jinja"),
                    paths.Filesystem("n2.jinja"),
                ),
                templates=(
                    paths.Filesystem("t1.jinja"),
                    paths.Filesystem("t2.jinja"),
                ),
            ),
            dict(
                source_paths=["src1", "src2"],
                build_paths=["build1", "build2"],
                python_paths=["src1/py", "src2/py"],
            ),
            config.Minimal(
                source_paths=(
                    paths.Filesystem("src1"),
                    paths.Filesystem("src2"),
                ),
                build_paths=(
                    paths.Filesystem("build1"),
                    paths.Filesystem("build2"),
                ),
                python_paths=(
                    paths.Filesystem("src1/py"),
                    paths.Filesystem("src2/py"),
                ),
            ),
        ),
        (
            # Minimal's fields are normalized.
            dict(
                source_paths=["src2", "src2", "src1"],
                build_paths=["build2", "build2", "build1"],
                python_paths=[],
            ),
            config.Config(
                source_paths=(
                    paths.Filesystem("src1"),
                    paths.Filesystem("src2"),
                ),
                build_paths=(
                    paths.Filesystem("build1"),
                    paths.Filesystem("build2"),
                ),
                python_paths=(),
                ninja_templates=(),
                templates=(),
            ),
            dict(
                source_paths=["src1", "src2"],
                build_paths=["build1", "build2"],
                python_paths=[],
            ),
            config.Minimal(
                source_paths=(
                    paths.Filesystem("src1"),
                    paths.Filesystem("src2"),
                ),
                build_paths=(
                    paths.Filesystem("build1"),
                    paths.Filesystem("build2"),
                ),
                python_paths=(),
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
