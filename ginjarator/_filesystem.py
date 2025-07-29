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
from collections.abc import Callable, Collection, Set
import json
import pathlib
import tomllib
from typing import Any, Literal, overload, override

from ginjarator import _config
from ginjarator import _paths


def _is_relative_to_any(
    path: pathlib.PurePath,
    others: Collection[pathlib.PurePath],
) -> bool:
    return any(path.is_relative_to(other) for other in others)


def _check_allowed(
    path: _paths.Filesystem,
    *,
    allowed_now: Collection[_paths.Filesystem] = (),
    allowed_now_exact: Collection[_paths.Filesystem] = (),
    allowed_deferred: Collection[_paths.Filesystem] = (),
    defer_ok: bool,
) -> bool:
    # NOTE: This is meant to prevent mistakes that could make builds less
    # reliable. It is not meant to be, and isn't, secure.
    if path in allowed_now_exact or _is_relative_to_any(path, allowed_now):
        return True
    elif _is_relative_to_any(path, allowed_deferred):
        if defer_ok:
            return False
        else:
            raise ValueError(
                f"{str(path)!r} is not allowed in this pass and deferring to a "
                "later pass is disabled."
            )
    else:
        if defer_ok:
            allowed = sorted(
                map(str, {*allowed_now, *allowed_now_exact, *allowed_deferred})
            )
        else:
            allowed = sorted(map(str, {*allowed_now, *allowed_now_exact}))
        raise ValueError(f"{str(path)!r} is not in allowed paths: {allowed}")


class Mode(abc.ABC):
    """How the filesystem can be accessed."""

    def __init__(self) -> None:
        self._minimal_config: _config.Minimal | None = None

    def use_cache_to_configure(self) -> bool:
        """Whether the minimal config should be read from cache."""
        return True

    def configure(
        self,
        *,
        minimal_config: _config.Minimal,
    ) -> None:
        """Configures the mode for use by a Filesystem."""
        if self._minimal_config is not None:
            raise ValueError("Already configured.")
        self._minimal_config = minimal_config

    @property
    def minimal_config(self) -> _config.Minimal:
        """Minimal config."""
        if self._minimal_config is None:
            raise ValueError("Not configured yet.")
        return self._minimal_config

    @abc.abstractmethod
    def check_read(self, path: _paths.Filesystem, *, defer_ok: bool) -> bool:
        """Checks if the path can be read.

        Args:
            path: Path to check.
            defer_ok: Whether deferring to another pass is allowed.

        Returns:
            True if the path can be read now; False if the path can't be read
            now but should be deferred to another pass.

        Raises:
            Exception: The path isn't allowed.
        """

    @abc.abstractmethod
    def check_write(self, path: _paths.Filesystem, *, defer_ok: bool) -> bool:
        """Checks if the path can be written.

        Args:
            path: Path to check.
            defer_ok: Whether deferring to another pass is allowed.

        Returns:
            True if the path can be written now; False if the path can't be
            written now but should be deferred to another pass.

        Raises:
            Exception: The path isn't allowed.
        """


class InternalMode(Mode):
    """Access by ginjarator itself, not templates."""

    @override
    def use_cache_to_configure(self) -> bool:
        return False

    @override
    def check_read(self, path: _paths.Filesystem, *, defer_ok: bool) -> bool:
        return _check_allowed(
            path,
            allowed_now=(
                _paths.INTERNAL,
                *self.minimal_config.source_paths,
            ),
            allowed_now_exact=(_paths.CONFIG,),
            defer_ok=False,
        )

    @override
    def check_write(self, path: _paths.Filesystem, *, defer_ok: bool) -> bool:
        return _check_allowed(
            path,
            allowed_now=(_paths.INTERNAL,),
            allowed_now_exact=(_paths.NINJA_ENTRYPOINT,),
            defer_ok=False,
        )


class NinjaMode(Mode):
    """Render a template containing custom ninja code.

    * Any source path can be read.
    * No writing is allowed.
    """

    @override
    def use_cache_to_configure(self) -> bool:
        # Ninja templates are rendered during init, which also writes the
        # minimal config cache. This prevents circular dependencies.
        return False

    @override
    def check_read(self, path: _paths.Filesystem, *, defer_ok: bool) -> bool:
        return _check_allowed(
            path,
            allowed_now=self.minimal_config.source_paths,
            allowed_now_exact=(_paths.CONFIG,),
            defer_ok=False,
        )

    @override
    def check_write(self, path: _paths.Filesystem, *, defer_ok: bool) -> bool:
        return _check_allowed(path, defer_ok=False)


class ScanMode(Mode):
    """Scan templates to find their dependencies and outputs.

    * Any source path can be read now.
    * Any build path can be deferred to read or write later.
    """

    @override
    def check_read(self, path: _paths.Filesystem, *, defer_ok: bool) -> bool:
        return _check_allowed(
            path,
            allowed_now=self.minimal_config.source_paths,
            allowed_now_exact=(
                _paths.CONFIG,
                _paths.MINIMAL_CONFIG,
            ),
            allowed_deferred=self.minimal_config.build_paths,
            defer_ok=defer_ok,
        )

    @override
    def check_write(self, path: _paths.Filesystem, *, defer_ok: bool) -> bool:
        return _check_allowed(
            path,
            allowed_deferred=self.minimal_config.build_paths,
            defer_ok=defer_ok,
        )


class TestScanMode(ScanMode):
    """ScanMode for use in external project tests."""

    @override
    def use_cache_to_configure(self) -> bool:
        return False


class RenderMode(Mode):
    """Render templates, using the results from a scan pass.

    * Any (deferred) read from the scan pass can be read.
    * Any deferred write from the scan pass can be written.
    """

    def __init__(
        self,
        *,
        dependencies: Collection[_paths.Filesystem] = (),
        outputs: Collection[_paths.Filesystem] = (),
    ) -> None:
        """Initializer.

        Args:
            dependencies: (Deferred) reads from the scan pass.
            outputs: Deferred writes from the scan pass.
        """
        super().__init__()
        self._dependencies = frozenset(dependencies)
        self._outputs = frozenset(outputs)
        self._scan_mode = ScanMode()

    @override
    def configure(self, *args: Any, **kwargs: Any) -> None:
        super().configure(*args, **kwargs)
        self._scan_mode.configure(*args, **kwargs)

    @override
    def check_read(self, path: _paths.Filesystem, *, defer_ok: bool) -> bool:
        self._scan_mode.check_read(path, defer_ok=True)
        return _check_allowed(
            path,
            allowed_now_exact=self._dependencies,
            defer_ok=False,
        )

    @override
    def check_write(self, path: _paths.Filesystem, *, defer_ok: bool) -> bool:
        self._scan_mode.check_write(path, defer_ok=True)
        return _check_allowed(
            path,
            allowed_now_exact=self._outputs,
            defer_ok=False,
        )


class TestRenderMode(RenderMode):
    """RenderMode for use in external project tests."""

    @override
    def use_cache_to_configure(self) -> bool:
        return False


class Filesystem:
    """Interface to the filesystem.

    Attributes:
        root: Top-level path of the project.
    """

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
        self.root = root
        self._mode = InternalMode() if mode is None else mode

        # This has to use pathlib.Path.read_text() instead of self.read_text()
        # because of the circular dependency otherwise. The dependency is added
        # below.
        if self._mode.use_cache_to_configure():
            minimal_config_loaded_from = _paths.MINIMAL_CONFIG
            self._minimal_config = _config.Minimal.parse(
                json.loads((self.root / minimal_config_loaded_from).read_text())
            )
        else:
            minimal_config_loaded_from = _paths.CONFIG
            self._minimal_config = _config.Minimal.parse(
                _config.Config.parse(
                    tomllib.loads(
                        (self.root / minimal_config_loaded_from).read_text()
                    )
                ).serialize_minimal()
            )
        self._mode.configure(minimal_config=self._minimal_config)

        self._dependencies = set[_paths.Filesystem]()
        self._deferred_dependencies = set[_paths.Filesystem]()
        self._outputs = set[_paths.Filesystem]()
        self._deferred_outputs = set[_paths.Filesystem]()

        # This has to be after everything is initialized.
        self.add_dependency(minimal_config_loaded_from, defer_ok=False)

    @property
    def dependencies(self) -> Set[_paths.Filesystem]:
        """Files that were read."""
        return frozenset(self._dependencies)

    @property
    def deferred_dependencies(self) -> Set[_paths.Filesystem]:
        """Files that were deferred to be read in another pass."""
        return frozenset(self._deferred_dependencies)

    @property
    def outputs(self) -> Set[_paths.Filesystem]:
        """Files that were written."""
        return frozenset(self._outputs)

    @property
    def deferred_outputs(self) -> Set[_paths.Filesystem]:
        """Files that were deferred to be written in another pass."""
        return frozenset(self._deferred_outputs)

    def add_dependency(
        self,
        path: _paths.Filesystem | str,
        *,
        defer_ok: bool = True,
    ) -> bool:
        """Adds a dependency.

        Args:
            path: Path to add as a dependency.
            defer_ok: If False and the file can't be read yet, raise an
                exception.

        Returns:
            Whether the file can be read yet.
        """
        path = _paths.Filesystem(path)
        if self._mode.check_read(path, defer_ok=defer_ok):
            self._dependencies.add(path)
            return True
        else:
            self._deferred_dependencies.add(path)
            return False

    @overload
    def read_text(
        self,
        path: _paths.Filesystem | str,
        *,
        defer_ok: Literal[False],
    ) -> str: ...
    @overload
    def read_text(
        self,
        path: _paths.Filesystem | str,
        *,
        defer_ok: bool = True,
    ) -> str | None: ...
    def read_text(
        self,
        path: _paths.Filesystem | str,
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
        if not self.add_dependency(_paths.Filesystem(path), defer_ok=defer_ok):
            assert defer_ok
            return None
        return (self.root / path).read_text()

    def read_minimal_config(self) -> _config.Minimal:
        """Returns a minimal subset of the config."""
        return self._minimal_config

    def read_config(self) -> _config.Config:
        """Returns the config."""
        return _config.Config.parse(
            tomllib.loads(self.read_text(_paths.CONFIG, defer_ok=False))
        )

    def _add_output(
        self,
        path: _paths.Filesystem,
        *,
        defer_ok: bool,
    ) -> bool:
        if self._mode.check_write(path, defer_ok=defer_ok):
            self._outputs.add(path)
            return True
        else:
            self._deferred_outputs.add(path)
            return False

    def add_output(
        self,
        path: _paths.Filesystem | str,
        *,
        defer_ok: bool = True,
    ) -> None:
        """Adds an output."""
        self._add_output(_paths.Filesystem(path), defer_ok=defer_ok)

    def write_text(
        self,
        path: _paths.Filesystem | str,
        contents: str,
        *,
        defer_ok: bool = True,
    ) -> None:
        """Writes a string to a file, or adds the file as an output for later.

        Args:
            path: Path to write to.
            contents: String to write.
            defer_ok: When the file can't be written now but can be added as an
                output to write in another pass: If True, add the output and
                succeed silently; if False, raise an exception.
        """
        if not self._add_output(_paths.Filesystem(path), defer_ok=defer_ok):
            assert defer_ok
            return
        full_path = self.root / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(contents)

    def write_text_macro(
        self,
        path: _paths.Filesystem | str,
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
