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
import tomllib
import urllib.parse

from ginjarator import config

CONFIG_FILE = pathlib.Path("ginjarator.toml")
BUILD_FILE = pathlib.Path("build.ninja")
_INTERNAL_DIR = pathlib.Path(".ginjarator")


def _is_relative_to_any(
    path: pathlib.Path,
    others: Collection[pathlib.Path],
) -> bool:
    return any(path.is_relative_to(other) for other in others)


def _check_allowed(
    path: pathlib.Path,
    allowed_paths: Collection[pathlib.Path],
) -> None:
    # NOTE: This is meant to prevent mistakes that could make builds less
    # reliable. It is not meant to be, and isn't, secure.
    if not _is_relative_to_any(path, allowed_paths):
        raise ValueError(
            f"{str(path)!r} is not in allowed paths: {sorted(allowed_paths)}"
        )


class Filesystem:
    """Interface to source and build paths in the filesystem.

    In source paths, reading is always allowed and writing is never allowed. In
    build paths, reading is only allowed for paths in build_done_paths and
    writing is always allowed.
    """

    def __init__(
        self,
        root: pathlib.Path = pathlib.Path("."),
        *,
        build_done_paths: Collection[pathlib.Path] = (),
    ) -> None:
        """Initializer.

        Args:
            root: Top-level path of the project.
            build_done_paths: Which files/directories from build paths have
                already finished building.
        """
        self._root = root

        # This has to use pathlib.Path.read_text() instead of self.read_text()
        # because of the circular dependency otherwise. In theory, every
        # template should depend on the config file, but I think in most
        # circumstances the extra rebuilding wouldn't be worth the extra
        # correctness. If that turns out to be wrong, self.add_dependency() can
        # be called after the path attributes are initialized below.
        config_ = config.Config.parse(
            tomllib.loads(self.resolve(CONFIG_FILE).read_text())
        )

        self._source_paths = frozenset(map(self.resolve, config_.source_paths))
        self._build_paths = frozenset(map(self.resolve, config_.build_paths))
        self._build_done_paths = frozenset(map(self.resolve, build_done_paths))

        # Prevent accidentally using anything other than the paths from the
        # config object, without adding a dependency on it first.
        del config_

        if any(
            _is_relative_to_any(source_path, self._build_paths)
            for source_path in self._source_paths
        ) or any(
            _is_relative_to_any(build_path, self._source_paths)
            for build_path in self._build_paths
        ):
            raise ValueError("Source and build paths must not overlap.")

        self._readable_ever_paths = frozenset(
            (
                self.resolve(CONFIG_FILE),
                self.resolve(_INTERNAL_DIR),
                *self._source_paths,
                *self._build_paths,
            )
        )
        self._readable_now_paths = frozenset(
            (
                self.resolve(CONFIG_FILE),
                self.resolve(_INTERNAL_DIR),
                *self._source_paths,
                *self._build_done_paths,
            )
        )
        self._writable_paths = frozenset(
            (
                self.resolve(BUILD_FILE),
                self.resolve(_INTERNAL_DIR),
                *self._build_paths,
            )
        )

        self._dependencies = set[pathlib.Path]()
        self._outputs = set[pathlib.Path]()

    @property
    def dependencies(self) -> Collection[pathlib.Path]:
        """Files that were read, or will be read in another pass."""
        return frozenset(self._dependencies)

    @property
    def outputs(self) -> Collection[pathlib.Path]:
        """Files that were written, or will be written in another pass."""
        return frozenset(self._outputs)

    def resolve(self, path: pathlib.Path | str) -> pathlib.Path:
        """Returns the canonical full path."""
        return (self._root / path).resolve()

    def add_dependency(self, path: pathlib.Path | str) -> None:
        """Adds a dependency."""
        full_path = self.resolve(path)
        _check_allowed(full_path, self._readable_ever_paths)
        self._dependencies.add(full_path)

    def read_text(self, path: pathlib.Path | str) -> str | None:
        """Returns the contents of a file, or None if it's not built yet."""
        full_path = self.resolve(path)
        _check_allowed(full_path, self._readable_ever_paths)
        self._dependencies.add(full_path)
        if _is_relative_to_any(full_path, self._readable_now_paths):
            return full_path.read_text()
        else:
            return None

    def read_config(self) -> config.Config:
        """Returns the config."""
        contents = self.read_text(CONFIG_FILE)
        assert contents is not None  # CONFIG_FILE is always readable.
        return config.Config.parse(tomllib.loads(contents))

    def add_output(self, path: pathlib.Path | str) -> None:
        """Adds an output."""
        full_path = self.resolve(path)
        _check_allowed(full_path, self._writable_paths)
        self._outputs.add(full_path)

    def write_text(self, path: pathlib.Path | str, contents: str) -> None:
        """Writes a string to a file, preserving mtime if nothing changed."""
        full_path = self.resolve(path)
        _check_allowed(full_path, self._writable_paths)
        self._outputs.add(full_path)
        try:
            if contents == full_path.read_text():
                return
        except FileNotFoundError:
            pass
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(contents)

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


def template_state_path(template_name: pathlib.Path | str) -> pathlib.Path:
    """Returns the path for template state."""
    return internal_path("templates", f"{template_name}.json")
