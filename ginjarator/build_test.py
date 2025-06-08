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

from ginjarator import build


@pytest.mark.parametrize(
    "value,expected",
    (
        ("foo: $bar", "foo$:$ $$bar"),
        (["foo", "bar"], "foo bar"),
        (("foo", "bar"), "foo bar"),
        ({"foo", "bar"}, "bar foo"),
        (frozenset(("foo", "bar")), "bar foo"),
    ),
)
def test_to_ninja(value: Any, expected: str) -> None:
    assert build.to_ninja(value) == expected


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
        build.to_ninja(value)
