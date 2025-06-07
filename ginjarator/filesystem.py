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
    """Interface to source and build paths in the filesystem.

    Attributes:
        dependencies: Files that either were read, or will be read during the
            build step.
        outputs: Files that either were written, or will be written during the
            build step.
    """

    def __init__(
        self,
        root: pathlib.Path = pathlib.Path("."),
        *,
        read_allow: Collection[pathlib.Path],
        write_allow: Collection[pathlib.Path],
    ) -> None:
        """Initializer.

        Args:
            root: Top-level path of the project.
            read_allow: Where files can be read from.
            write_allow: Where files can be written to.
        """
        self._root = root
        self._read_allow = frozenset(
            (root / path).resolve() for path in read_allow
        )
        self._write_allow = frozenset(
            (root / path).resolve() for path in write_allow
        )
        self.dependencies = set[pathlib.Path]()
        self.outputs = set[pathlib.Path]()

    def read_text(self, path: pathlib.Path) -> str:
        """Returns the contents of a file."""
        full_path = (self._root / path).resolve()
        if not any(
            full_path.is_relative_to(allowed) for allowed in self._read_allow
        ):
            raise ValueError(
                f"{str(path)!r} is not in allowed read paths: "
                f"{sorted(self._read_allow)}"
            )
        self.dependencies.add(full_path)
        return full_path.read_text()

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
        self.outputs.add(full_path)
        try:
            if contents == full_path.read_text():
                return
        except FileNotFoundError:
            pass
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(contents)
