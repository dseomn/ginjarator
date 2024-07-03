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

import time
import pathlib

from absl.testing import absltest
from absl.testing import parameterized

from ginjarator import filesystem


class FilesystemTest(parameterized.TestCase):

    def setUp(self):
        super().setUp()
        self._root = pathlib.Path(self.create_tempdir().full_path)
        self._fs = filesystem.Filesystem(self._root)

    @parameterized.parameters("src/foo", "something-else", "/absolute")
    def test_write_text_invalid_path(self, path: str):
        with self.assertRaisesRegex(ValueError, "can be written to"):
            self._fs.write_text(pathlib.Path(path), "foo")

    def test_write_text_noop(self):
        contents = "the contents of the file"
        path = pathlib.Path("build/some-file")
        full_path = self._root / path
        full_path.parent.mkdir(parents=True)
        full_path.write_text(contents)
        original_mtime = full_path.stat().st_mtime

        self._fs.write_text(path, contents)

        self.assertEqual(contents, full_path.read_text())
        self.assertEqual(original_mtime, full_path.stat().st_mtime)

    def test_write_text_writes_new_file(self):
        contents = "the contents of the file"
        path = pathlib.Path("build/some-file")
        full_path = self._root / path

        self._fs.write_text(path, contents)

        self.assertEqual(contents, full_path.read_text())

    def test_write_text_updates_file(self):
        contents = "the contents of the file"
        path = pathlib.Path("build/some-file")
        full_path = self._root / path
        full_path.parent.mkdir(parents=True)
        full_path.write_text("original contents of the file")
        original_mtime = full_path.stat().st_mtime
        # Prevent the two different write_text() calls from appearing to happen
        # at the same time.
        time.sleep(0.01)

        self._fs.write_text(path, contents)

        self.assertEqual(contents, full_path.read_text())
        self.assertLess(original_mtime, full_path.stat().st_mtime)


if __name__ == "__main__":
    absltest.main()
