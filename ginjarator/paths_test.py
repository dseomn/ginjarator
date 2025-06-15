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

import re

from ginjarator import paths


def test_internal() -> None:
    assert re.fullmatch(
        r"\.ginjarator/dependencies/foo%2[Ff]bar\.json",
        str(paths.internal("dependencies", "foo/bar.json")),
    )


def test_ninja_template_output() -> None:
    assert paths.ninja_template_output("foo") == paths.Filesystem(
        ".ginjarator/ninja_templates/foo.ninja"
    )


def test_template_state() -> None:
    assert paths.template_state("foo") == paths.Filesystem(
        ".ginjarator/templates/foo.json"
    )


def test_template_depfile() -> None:
    assert paths.template_depfile("foo") == paths.Filesystem(
        ".ginjarator/templates/foo.d"
    )


def test_template_dyndep() -> None:
    assert paths.template_dyndep("foo") == paths.Filesystem(
        ".ginjarator/templates/foo.dd"
    )


def test_template_render_stamp() -> None:
    assert paths.template_render_stamp("foo") == paths.Filesystem(
        ".ginjarator/templates/foo.render-stamp"
    )
