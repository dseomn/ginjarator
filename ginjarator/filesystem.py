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

import pathlib


class Filesystem:
    """Interface to source and build paths in the filesystem.

    Attributes:
        src: Path to source files.
        build: Path to build files.
    """

    def __init__(self, root: pathlib.Path = pathlib.Path(".")) -> None:
        self._root = root
        self.src = (root / "src").resolve()
        self.build = (root / "build").resolve()

    def write_text(self, path: pathlib.Path, contents: str) -> None:
        """Writes a string to a file, preserving mtime if nothing changed."""
        full_path = (self._root / path).resolve()
        if not full_path.is_relative_to(self.build):
            raise ValueError(
                f"Only the build directory can be written to, not {str(path)!r}"
            )
        try:
            if contents == full_path.read_text():
                return
        except FileNotFoundError:
            pass
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(contents)
