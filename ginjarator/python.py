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
"""Python code use by templates."""

import builtins
from collections.abc import Mapping, Sequence
import contextvars
import pathlib
import sys
import types
from typing import Never

from ginjarator import filesystem
from ginjarator import paths

# See
# https://discuss.python.org/t/tracking-and-isolating-imports-without-sys-modules-caching/95418
# for discussion about the approach this file uses for tracking imports.

_imported_origins: contextvars.ContextVar[set[str]] = contextvars.ContextVar(
    "_imported_origins"
)

_original_import = builtins.__import__


def _import_wrapper(
    name: str,
    globals: (  # pylint: disable=redefined-builtin
        Mapping[str, object] | None
    ) = None,
    locals: (  # pylint: disable=redefined-builtin
        Mapping[str, object] | None
    ) = None,
    fromlist: Sequence[str] = (),
    level: int = 0,
) -> types.ModuleType:
    """__import__ wrapper that tracks __spec__.origin of imported modules."""
    imported = _original_import(name, globals, locals, fromlist, level)
    imported_origins = _imported_origins.get(None)
    if imported_origins is None:
        return imported
    named_module = imported
    if not fromlist:
        for attr in name.split(".")[1:]:
            named_module = getattr(named_module, attr)
    modules = [named_module]
    # The type signature says fromlist can't be None, but sometimes it is.
    if fromlist is not None:
        for attr in fromlist:
            maybe_module = getattr(named_module, attr)
            if isinstance(maybe_module, types.ModuleType):
                modules.append(maybe_module)
    for module in modules:
        if module.__spec__ is not None and module.__spec__.origin is not None:
            imported_origins.add(module.__spec__.origin)
    return imported


builtins.__import__ = _import_wrapper


class TemplateError(Exception):
    """Exception raised manually by templates."""


class Api:
    """API for using python code from templates."""

    def __init__(self, *, fs: filesystem.Filesystem) -> None:
        self._fs = fs
        self._python_fs_by_resolved_path = {}

        # It would be nice if this didn't affect global state, but this seems
        # simpler than any other option I'm aware of.
        for path in self._fs.read_minimal_config().python_paths:
            resolved = (self._fs.root / path).resolve()
            self._python_fs_by_resolved_path[resolved] = path
            if str(resolved) not in sys.path:
                sys.path.append(str(resolved))

    def module(self, name: str) -> types.ModuleType:
        """Returns a module."""
        imported_origins = set[str]()
        imported_origins_token = _imported_origins.set(imported_origins)
        try:
            # It seems that importlib.import_module() doesn't use the __import__
            # wrapper above, so this uses __import__ instead.
            module = __import__(name)
        finally:
            _imported_origins.reset(imported_origins_token)
        for attr in name.split(".")[1:]:
            module = getattr(module, attr)

        for origin in imported_origins:
            origin_resolved = pathlib.Path(origin).resolve()
            for (
                python_resolved,
                python_fs,
            ) in self._python_fs_by_resolved_path.items():
                if origin_resolved.is_relative_to(python_resolved):
                    self._fs.add_dependency(
                        paths.Filesystem(
                            python_fs
                            / origin_resolved.relative_to(python_resolved)
                        ),
                        defer_ok=False,
                    )
                    break

        return module

    def raise_(self, *args: object) -> Never:
        """Raises an exception."""
        raise TemplateError(*args)
