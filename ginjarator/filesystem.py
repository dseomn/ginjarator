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
"""Tools for reading source files and writing build outputs."""

from collections.abc import Collection
import pathlib


class Filesystem:
    """Interface to source and build paths in the filesystem."""

    def __init__(
        self,
        root: pathlib.Path = pathlib.Path("."),
        *,
        write_allow: Collection[pathlib.Path],
    ) -> None:
        """Initializer.

        Args:
            root: Top-level path of the project.
            write_allow: Where files can be written to.
        """
        self._root = root
        self._write_allow = frozenset(
            (root / path).resolve() for path in write_allow
        )

    def write_text(self, path: pathlib.Path, contents: str) -> None:
        """Writes a string to a file, preserving mtime if nothing changed."""
        full_path = (self._root / path).resolve()
        if not any(
            full_path.is_relative_to(allowed) for allowed in self._write_allow
        ):
            raise ValueError(
                f"{str(path)!r} is not in allowed write paths: "
                f"{sorted(self._write_allow)}"
            )
        try:
            if contents == full_path.read_text():
                return
        except FileNotFoundError:
            pass
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(contents)
