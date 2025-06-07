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

# pylint: disable=missing-module-docstring

import pathlib
import time

import pytest

from ginjarator import filesystem


def _sleep_for_mtime() -> None:
    """Prevents writes before/after calling this from having the same mtime."""
    time.sleep(0.01)


@pytest.mark.parametrize(
    "path",
    (
        "src/foo",
        "something-else",
        "/absolute",
    ),
)
def test_write_text_invalid_path(
    path: str,
    tmp_path: pathlib.Path,
) -> None:
    fs = filesystem.Filesystem(tmp_path)

    with pytest.raises(ValueError, match="can be written to"):
        fs.write_text(pathlib.Path(path), "foo")


def test_write_text_noop(tmp_path: pathlib.Path) -> None:
    fs = filesystem.Filesystem(tmp_path)
    contents = "the contents of the file"
    path = pathlib.Path("build/some-file")
    full_path = tmp_path / path
    full_path.parent.mkdir(parents=True)
    full_path.write_text(contents)
    original_mtime = full_path.stat().st_mtime
    _sleep_for_mtime()

    fs.write_text(path, contents)

    assert full_path.read_text() == contents
    assert full_path.stat().st_mtime == original_mtime


def test_write_text_writes_new_file(tmp_path: pathlib.Path) -> None:
    fs = filesystem.Filesystem(tmp_path)
    contents = "the contents of the file"
    path = pathlib.Path("build/some-file")
    full_path = tmp_path / path

    fs.write_text(path, contents)

    assert full_path.read_text() == contents


def test_write_text_updates_file(tmp_path: pathlib.Path) -> None:
    fs = filesystem.Filesystem(tmp_path)
    contents = "the contents of the file"
    path = pathlib.Path("build/some-file")
    full_path = tmp_path / path
    full_path.parent.mkdir(parents=True)
    full_path.write_text("original contents of the file")
    original_mtime = full_path.stat().st_mtime
    _sleep_for_mtime()

    fs.write_text(path, contents)

    assert full_path.read_text() == contents
    assert full_path.stat().st_mtime > original_mtime
