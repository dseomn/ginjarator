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
"""Build system."""

import pathlib
import shlex
from typing import Any


def to_ninja(value: Any, *, escape_shell: bool) -> str:
    """Returns a value in ninja's syntax."""
    # https://ninja-build.org/manual.html#ref_lexer
    match value:
        case str() if escape_shell:
            return to_ninja(shlex.quote(value), escape_shell=False)
        case str() if not set(value) & set("#\n"):
            return value.translate(
                str.maketrans(
                    dict[str, int | str | None](
                        {
                            " ": "$ ",
                            ":": "$:",
                            "$": "$$",
                        }
                    )
                )
            )
        case pathlib.Path():
            return to_ninja(str(value), escape_shell=escape_shell)
        case list() | tuple():
            return " ".join(
                to_ninja(item, escape_shell=escape_shell) for item in value
            )
        case set() | frozenset():
            return to_ninja(sorted(value), escape_shell=escape_shell)
        case _:
            raise NotImplementedError(
                f"Can't convert {value!r} to ninja syntax."
            )
