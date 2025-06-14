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

import abc
from collections.abc import Callable, Collection
import pathlib
import tomllib
from typing import Any, Literal, Never, overload, override
import urllib.parse

from ginjarator import config

CONFIG_PATH = pathlib.Path("ginjarator.toml")
BUILD_PATH = pathlib.Path("build.ninja")
INTERNAL_DIR = pathlib.Path(".ginjarator")


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


def _forbid_all(path: pathlib.Path) -> Never:
    raise ValueError(f"{str(path)!r} is not in allowed paths: {()}")


class Mode(abc.ABC):
    """How the filesystem can be accessed."""

    def __init__(self) -> None:
        self._configured = False
        self._minimal_config: config.Minimal | None = None
        self._resolve: Callable[[pathlib.Path | str], pathlib.Path] | None = (
            None
        )

    def configure(
        self,
        *,
        minimal_config: config.Minimal,
        resolve: Callable[[pathlib.Path | str], pathlib.Path],
    ) -> None:
        """Configures the mode for use by a Filesystem."""
        if self._configured:
            raise ValueError("Already configured.")
        self._configured = True
        self._minimal_config = minimal_config
        self._resolve = resolve

    @property
    def minimal_config(self) -> config.Minimal:
        """Minimal config."""
        if self._minimal_config is None:
            raise ValueError("Not configured yet.")
        return self._minimal_config

    def resolve(self, path: pathlib.Path | str) -> pathlib.Path:
        """Filesystem.resolve()."""
        if self._resolve is None:
            raise ValueError("Not configured yet.")
        return self._resolve(path)

    @abc.abstractmethod
    def check_dependency(self, path: pathlib.Path) -> None:
        """Raises an exception if path can't be added as a dependency."""

    @abc.abstractmethod
    def check_read(self, path: pathlib.Path) -> bool:
        """Checks if the path can be read.

        Args:
            path: Path to check.

        Returns:
            True if the path can be read now; False if the path can't be read
            now but should be added as a dependency for later.

        Raises:
            Exception: The path isn't allowed.
        """

    @abc.abstractmethod
    def check_output(self, path: pathlib.Path) -> None:
        """Raises an exception if path can't be added as an output."""

    @abc.abstractmethod
    def check_write(self, path: pathlib.Path) -> bool:
        """Checks if the path can be written.

        Args:
            path: Path to check.

        Returns:
            True if the path can be written now; False if the path can't be
            written now but should be added as an output for later.

        Raises:
            Exception: The path isn't allowed.
        """


class InternalMode(Mode):
    """Access by ginjarator itself, not templates."""

    @override
    def check_dependency(self, path: pathlib.Path) -> None:
        _check_allowed(
            path,
            (
                self.resolve(CONFIG_PATH),
                self.resolve(INTERNAL_DIR),
                *self.minimal_config.source_paths,
            ),
        )

    @override
    def check_read(self, path: pathlib.Path) -> bool:
        self.check_dependency(path)
        return True

    @override
    def check_output(self, path: pathlib.Path) -> None:
        _check_allowed(
            path,
            (
                self.resolve(BUILD_PATH),
                self.resolve(INTERNAL_DIR),
            ),
        )

    @override
    def check_write(self, path: pathlib.Path) -> bool:
        self.check_output(path)
        return True


class NinjaMode(Mode):
    """Render a template containing custom ninja code.

    * Any source path can be added as a dependency or read.
    * No outputs or writing are allowed.
    """

    @override
    def check_dependency(self, path: pathlib.Path) -> None:
        _check_allowed(
            path,
            (
                self.resolve(CONFIG_PATH),
                *self.minimal_config.source_paths,
            ),
        )

    @override
    def check_read(self, path: pathlib.Path) -> bool:
        self.check_dependency(path)
        return True

    @override
    def check_output(self, path: pathlib.Path) -> None:
        _forbid_all(path)

    @override
    def check_write(self, path: pathlib.Path) -> bool:
        _forbid_all(path)


class ScanMode(Mode):
    """Scan templates to find their dependencies and outputs.

    * Any source or build path can be added as a dependency.
    * Any source path can be read, which implicitly adds it as a dependency.
    * Any build path can be added as an output.
    * No writing is allowed.
    """

    @override
    def check_dependency(self, path: pathlib.Path) -> None:
        _check_allowed(
            path,
            (
                self.resolve(CONFIG_PATH),
                *self.minimal_config.source_paths,
                *self.minimal_config.build_paths,
            ),
        )

    @override
    def check_read(self, path: pathlib.Path) -> bool:
        self.check_dependency(path)
        return _is_relative_to_any(
            path,
            (
                self.resolve(CONFIG_PATH),
                *self.minimal_config.source_paths,
            ),
        )

    @override
    def check_output(self, path: pathlib.Path) -> None:
        _check_allowed(path, self.minimal_config.build_paths)

    @override
    def check_write(self, path: pathlib.Path) -> bool:
        self.check_output(path)
        return False


class RenderMode(Mode):
    """Render templates, using the results from a scan pass.

    * Any dependency from the scan pass can be marked as a dependency or
      read.
    * Any output from the scan pass can be marked as an output or written
      to.
    """

    def __init__(
        self,
        *,
        dependencies: Collection[pathlib.Path] = (),
        outputs: Collection[pathlib.Path] = (),
    ) -> None:
        """Initializer.

        Args:
            dependencies: Dependencies from the scan pass.
            outputs: Outputs from the scan pass.
        """
        super().__init__()
        self._dependencies = dependencies
        self._outputs = outputs
        self._scan_mode = ScanMode()

    @override
    def configure(self, *args: Any, **kwargs: Any) -> None:
        super().configure(*args, **kwargs)
        self._scan_mode.configure(*args, **kwargs)

    @override
    def check_dependency(self, path: pathlib.Path) -> None:
        self._scan_mode.check_dependency(path)
        _check_allowed(path, self._dependencies)

    @override
    def check_read(self, path: pathlib.Path) -> bool:
        self.check_dependency(path)
        return True

    @override
    def check_output(self, path: pathlib.Path) -> None:
        self._scan_mode.check_output(path)
        _check_allowed(path, self._outputs)

    @override
    def check_write(self, path: pathlib.Path) -> bool:
        self.check_output(path)
        return True


class Filesystem:
    """Interface to the filesystem."""

    def __init__(
        self,
        root: pathlib.Path = pathlib.Path("."),
        *,
        mode: Mode | None = None,
    ) -> None:
        """Initializer.

        Args:
            root: Top-level path of the project.
            mode: How the filesystem can be accessed, or None to use
                InternalMode.
        """
        self._root = root
        self._mode = InternalMode() if mode is None else mode

        # This has to use pathlib.Path.read_text() instead of self.read_text()
        # because of the circular dependency otherwise. In theory, every
        # template should depend on the config file, but I think in most
        # circumstances the extra rebuilding wouldn't be worth the extra
        # correctness. If that turns out to be wrong, self.add_dependency() can
        # be called after the path attributes are initialized below.
        config_ = config.Config.parse(
            tomllib.loads(self.resolve(CONFIG_PATH).read_text())
        )
        self._mode.configure(
            minimal_config=config.Minimal(
                source_paths=frozenset(map(self.resolve, config_.source_paths)),
                build_paths=frozenset(map(self.resolve, config_.build_paths)),
            ),
            resolve=self.resolve,
        )
        del config_

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
        self._mode.check_dependency(full_path)
        self._dependencies.add(full_path)

    @overload
    def read_text(
        self,
        path: pathlib.Path | str,
        *,
        defer_ok: Literal[False],
    ) -> str: ...
    @overload
    def read_text(
        self,
        path: pathlib.Path | str,
        *,
        defer_ok: bool = True,
    ) -> str | None: ...
    def read_text(
        self,
        path: pathlib.Path | str,
        *,
        defer_ok: bool = True,
    ) -> str | None:
        """Returns the contents of a file, or None if it might not be built yet.

        Args:
            path: Path to read.
            defer_ok: When the file can't be read now but can be added as a
                dependency to read in another pass: If True, add the dependency
                and return None; if False, raise an exception.
        """
        full_path = self.resolve(path)
        readable_now = self._mode.check_read(full_path)
        if not readable_now and not defer_ok:
            raise ValueError(
                f"{str(path)!r} can't be read in this pass and deferring to a "
                "later pass is disabled."
            )
        self._dependencies.add(full_path)
        if not readable_now:
            assert defer_ok
            return None
        return full_path.read_text()

    def read_config(self) -> config.Config:
        """Returns the config."""
        return config.Config.parse(
            tomllib.loads(self.read_text(CONFIG_PATH, defer_ok=False))
        )

    def add_output(self, path: pathlib.Path | str) -> None:
        """Adds an output."""
        full_path = self.resolve(path)
        self._mode.check_output(full_path)
        self._outputs.add(full_path)

    def write_text(
        self,
        path: pathlib.Path | str,
        contents: str,
        *,
        preserve_mtime: bool = True,
        defer_ok: bool = True,
    ) -> bool:
        """Writes a string to a file, or adds the file as an output for later.

        Args:
            path: Path to write to.
            contents: String to write.
            preserve_mtime: If True and the contents are unchanged, it doesn't
                update the mtime, to avoid rebuilding downstream targets.
            defer_ok: When the file can't be written now but can be added as an
                output to write in another pass: If True, add the output and
                succeed silently; if False, raise an exception.

        Returns:
            Whether the file or its metadata was modified or not.
        """
        full_path = self.resolve(path)
        writable_now = self._mode.check_write(full_path)
        if not writable_now and not defer_ok:
            raise ValueError(
                f"{str(path)!r} can't be written in this pass and deferring "
                "to a later pass is disabled."
            )
        self._outputs.add(full_path)
        if not writable_now:
            assert defer_ok
            return False
        try:
            if preserve_mtime and contents == full_path.read_text():
                return False
        except FileNotFoundError:
            pass
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(contents)
        return True

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
    return INTERNAL_DIR.joinpath(
        *(urllib.parse.quote(component, safe="") for component in components)
    )


def template_state_path(template_name: pathlib.Path | str) -> pathlib.Path:
    """Returns the path for template state."""
    return internal_path("templates", f"{template_name}.json")


def template_depfile_path(template_name: pathlib.Path | str) -> pathlib.Path:
    """Returns the path for a template's depfile."""
    return internal_path("templates", f"{template_name}.d")


def template_dyndep_path(template_name: pathlib.Path | str) -> pathlib.Path:
    """Returns the path for a template's dyndep file."""
    return internal_path("templates", f"{template_name}.dd")


def template_render_stamp_path(
    template_name: pathlib.Path | str,
) -> pathlib.Path:
    """Returns the path for a template's render stamp."""
    return internal_path("templates", f"{template_name}.render-stamp")
