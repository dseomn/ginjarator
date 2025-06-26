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
"""Public test framework.

This meant to be used to test python code in a ginjarator project.
"""

from collections.abc import Collection, Generator
import contextlib
import pathlib

from ginjarator import _filesystem
from ginjarator import _paths
from ginjarator import _template

_DEFAULT_CURRENT_TEMPLATE = pathlib.PurePath(
    "test-only--the-current-template-is-not-set"
)


@contextlib.contextmanager
def api_for_scan(
    *,
    current_template: pathlib.PurePath | str = _DEFAULT_CURRENT_TEMPLATE,
    root_path: pathlib.Path = pathlib.Path("."),
) -> Generator[None, None, None]:
    """Returns a context manager that sets ginjarator.api() for scan mode.

    Args:
        current_template: The template currently being rendered.
        root_path: Root path of the project.
    """
    with _template.set_api(
        _template.Api(
            current_template=_paths.Filesystem(current_template),
            fs=_filesystem.Filesystem(
                root_path,
                mode=_filesystem.TestScanMode(),
            ),
        )
    ):
        yield


@contextlib.contextmanager
def api_for_render(
    *,
    current_template: pathlib.PurePath | str = _DEFAULT_CURRENT_TEMPLATE,
    root_path: pathlib.Path = pathlib.Path("."),
    dependencies: Collection[pathlib.PurePath | str] = (),
    outputs: Collection[pathlib.PurePath | str] = (),
) -> Generator[None, None, None]:
    """Returns a context manager that sets ginjarator.api() for render mode.

    Args:
        current_template: The template currently being rendered.
        root_path: Root path of the project. By default, it's the current
            project's own path. If the default is used, outputs must be empty to
            prevent accidentally writing to the current project in a test.
        dependencies: Files that the scan pass read or marked for reading later.
        outputs: Files that the scan pass marked for writing later.
    """
    if root_path == pathlib.Path(".") and outputs:
        raise ValueError("Tests should not write to a real project.")
    with _template.set_api(
        _template.Api(
            current_template=_paths.Filesystem(current_template),
            fs=_filesystem.Filesystem(
                root_path,
                mode=_filesystem.TestRenderMode(
                    dependencies=tuple(
                        map(
                            _paths.Filesystem,
                            ("ginjarator.toml", *dependencies),
                        )
                    ),
                    outputs=tuple(map(_paths.Filesystem, outputs)),
                ),
            ),
        )
    ):
        yield
