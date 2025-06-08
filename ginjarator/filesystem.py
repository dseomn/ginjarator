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

from collections.abc import Callable, Collection
import pathlib
import urllib.parse

_INTERNAL_DIR = pathlib.Path(".ginjarator")


def _check_allowed(
    path: pathlib.Path,
    allowed_paths: Collection[pathlib.Path],
) -> None:
    # NOTE: This is meant to prevent mistakes that could make builds less
    # reliable. It is not meant to be, and isn't, secure.
    if not any(
        path.is_relative_to(allowed_path) for allowed_path in allowed_paths
    ):
        raise ValueError(
            f"{str(path)!r} is not in allowed paths: {sorted(allowed_paths)}"
        )


class Filesystem:
    """Interface to source and build paths in the filesystem."""

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
        self._read_allow = frozenset(map(self.resolve, read_allow))
        self._write_allow = frozenset(map(self.resolve, write_allow))
        self._any_allow = self._read_allow | self._write_allow
        self._dependencies = set[pathlib.Path]()
        self._outputs = set[pathlib.Path]()
        self._created = set[pathlib.Path]()

    @property
    def dependencies(self) -> Collection[pathlib.Path]:
        """Files that were read, or will be read during the build step."""
        return frozenset(self._dependencies)

    @property
    def outputs(self) -> Collection[pathlib.Path]:
        """Files that were written, or will be written during the build step."""
        return frozenset(self._outputs)

    def resolve(self, path: pathlib.Path | str) -> pathlib.Path:
        """Returns the canonical full path."""
        return (self._root / path).resolve()

    def add_dependency(self, path: pathlib.Path | str) -> None:
        """Adds a dependency."""
        full_path = self.resolve(path)
        _check_allowed(full_path, self._any_allow)
        self._dependencies.add(full_path)

    def read_text(self, path: pathlib.Path | str) -> str:
        """Returns the contents of a file."""
        full_path = self.resolve(path)
        _check_allowed(full_path, self._read_allow)
        self._dependencies.add(full_path)
        return full_path.read_text()

    def add_output(self, path: pathlib.Path | str) -> None:
        """Adds an output."""
        full_path = self.resolve(path)
        _check_allowed(full_path, self._write_allow)
        self._outputs.add(full_path)

    def write_text(self, path: pathlib.Path | str, contents: str) -> None:
        """Writes a string to a file, preserving mtime if nothing changed."""
        full_path = self.resolve(path)
        _check_allowed(full_path, self._write_allow)
        self._outputs.add(full_path)
        try:
            if contents == full_path.read_text():
                return
        except FileNotFoundError:
            new_file = True
        else:
            new_file = False
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(contents)
        if new_file:
            self._created.add(full_path)

    def write_text_macro(
        self,
        path: pathlib.Path | str,
        caller: Callable[[], str],
    ) -> str:
        """Calls write_text() with a jinja macro, and returns the text.

        Args:
            path: See write_text()
            caller: Body of a jinja template's {% call %} block.
        """
        contents = caller()
        self.write_text(path, contents)
        return contents

    def delete_created_files(self) -> None:
        """Deletes any new files that were created."""
        for full_path in self._created:
            full_path.unlink()


def internal_path(*components: str) -> pathlib.Path:
    """Returns a path for internal state.

    Args:
        *components: Path components. Each one is escaped to remove "/", so
            other paths can be used as single components. However, "." and ".."
            are not escaped.
    """
    return _INTERNAL_DIR.joinpath(
        *(urllib.parse.quote(component, safe="") for component in components)
    )


def template_state_path(template_name: str) -> pathlib.Path:
    """Returns the path for template state."""
    return internal_path("templates", f"{template_name}.json")
