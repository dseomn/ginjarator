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
"""Build system utilities."""

import pathlib
import shlex
from typing import Any, Collection, Mapping


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


def _depfile_escape(path: str | pathlib.Path) -> str:
    # The syntax does not seem to be well documented in any one place. The
    # Target Rules section of
    # https://pubs.opengroup.org/onlinepubs/9799919799/utilities/make.html
    # describes some of it, but not backslash handling.
    # https://github.com/ninja-build/ninja/blob/master/src/depfile_parser.in.cc
    # shows how ninja parses it, but from the comments it looks like that's not
    # the right syntax either and they might change it in the future. This code
    # just disallows potentially problematic characters as much as possible.
    if any(
        c.isspace() or not c.isprintable() or c in ':;#"\\' for c in str(path)
    ):
        raise NotImplementedError(
            f"Unsupported characters in path {str(path)!r}."
        )
    return str(path).replace("%", "\\%")


def to_depfile(
    dependency_map: Mapping[str | pathlib.Path, Collection[str | pathlib.Path]],
) -> str:
    """Returns depfile contents given a map from target to dependencies."""
    lines = []
    for target, dependencies in dependency_map.items():
        for dependency in dependencies:
            lines.append(
                f"{_depfile_escape(target)}: {_depfile_escape(dependency)}\n"
            )
    return "".join(lines)
