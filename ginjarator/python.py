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

import importlib
import types


class Api:
    """API for using python code from templates."""

    def module(self, name: str) -> types.ModuleType:
        """Returns a module."""
        # TODO: dseomn - Support importing local modules using a Filesystem
        # object to track dependencies.
        del self  # Unused.
        return importlib.import_module(name)
