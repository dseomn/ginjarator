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

# pylint: disable=missing-module-docstring

import pathlib

from ginjarator import init


def test_init(tmp_path: pathlib.Path) -> None:
    (tmp_path / "ginjarator.toml").write_text(
        "templates = ['src/template.jinja']"
    )

    init.init(root_path=tmp_path)

    # This test is very minimal because checking the contents of the ninja file
    # would be pretty complicated, and it would probably just become a change
    # detector. End-to-end tests that actually run ninja are more useful here.
    assert (tmp_path / ".ginjarator/.gitignore").exists()
    assert (tmp_path / ".ginjarator/main.ninja").exists()
    assert (tmp_path / "build.ninja").exists()
