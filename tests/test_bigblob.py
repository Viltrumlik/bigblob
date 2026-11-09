"""Haqiqiy git repo quriladi, katta fayl commit qilinib o'chiriladi."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "bigblob.py")

spec = importlib.util.spec_from_file_location("bigblob", SCRIPT)
bb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bb)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="bigblob-"))
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "T")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.tmp, check=True,
                              capture_output=True, text=True)

    def commit_file(self, rel, size, char="x"):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(char * size)
        self.git("add", rel)
        self.git("commit", "-q", "-m", "add " + rel)

    def remove(self, rel):
        self.git("rm", "-q", rel)
        self.git("commit", "-q", "-m", "remove " + rel)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, SCRIPT, self.tmp, *args],
                              capture_output=True, text=True)

    def blobs(self, *args):
        return json.loads(self.run_cli("--json", *args).stdout)["blobs"]


class FindingTest(Base):
    def test_the_biggest_blob_comes_first(self):
        self.commit_file("small.txt", 100)
        self.commit_file("big.bin", 300000, "b")
        self.commit_file("medium.bin", 50000, "m")
        self.assertEqual([b["path"] for b in self.blobs()][:2],
                         ["big.bin", "medium.bin"])

    def test_a_deleted_file_is_still_found_and_flagged(self):
        self.commit_file("dump.sql", 200000, "d")
        self.remove("dump.sql")
        self.commit_file("keep.txt", 10)
        found = {b["path"]: b for b in self.blobs()}
        self.assertIn("dump.sql", found)
        self.assertTrue(found["dump.sql"]["gone"])
        self.assertFalse(found["keep.txt"]["gone"])

    def test_only_gone_filters_to_the_dead_weight(self):
        self.commit_file("dump.sql", 200000, "d")
        self.remove("dump.sql")
        self.commit_file("keep.bin", 150000, "k")
        self.assertEqual([b["path"] for b in self.blobs("--only-gone")],
                         ["dump.sql"])

    def test_the_limit_is_respected(self):
        for i in range(5):
            self.commit_file("f%d.bin" % i, 1000 * (i + 1), chr(97 + i))
        self.assertEqual(len(self.blobs("-n", "2")), 2)

    def test_a_file_renamed_keeps_one_entry(self):
        self.commit_file("old.bin", 120000, "r")
        self.git("mv", "old.bin", "new.bin")
        self.git("commit", "-q", "-m", "rename")
        paths = [b["path"] for b in self.blobs()]
        self.assertEqual(len(paths), len(set(paths)))

    def test_the_repository_size_is_reported(self):
        self.commit_file("a.bin", 50000, "a")
        data = json.loads(self.run_cli("--json").stdout)
        self.assertGreater(data["repository_bytes"], 0)


class HumanTest(unittest.TestCase):
    def test_sizes_read_naturally(self):
        self.assertEqual(bb.human(512), "512 B")
        self.assertEqual(bb.human(2048), "2.0 KB")
        self.assertEqual(bb.human(5 * 1024 * 1024), "5.0 MB")
        self.assertEqual(bb.human(3 * 1024 ** 3), "3.0 GB")


class CliTest(Base):
    def test_a_normal_run_mentions_the_repository_size(self):
        self.commit_file("a.bin", 50000, "a")
        out = self.run_cli()
        self.assertEqual(out.returncode, 0)
        self.assertIn("repository on disk", out.stdout)

    def test_dead_weight_is_called_out_with_the_fix(self):
        self.commit_file("dump.sql", 200000, "d")
        self.remove("dump.sql")
        out = self.run_cli()
        self.assertIn("no longer in HEAD", out.stdout)
        self.assertIn("filter-repo", out.stdout)

    def test_outside_a_repository_it_says_so(self):
        plain = tempfile.mkdtemp(prefix="bigblob-plain-")
        self.addCleanup(shutil.rmtree, plain, True)
        out = subprocess.run([sys.executable, SCRIPT, plain],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 1)
        self.assertIn("not a git repository", out.stderr)

    def test_a_bad_limit_is_a_usage_error(self):
        self.assertEqual(self.run_cli("-n", "0").returncode, 2)

    def test_a_missing_folder_is_a_usage_error(self):
        out = subprocess.run([sys.executable, SCRIPT, os.path.join(self.tmp, "no")],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)

    def test_an_empty_repository_does_not_crash(self):
        empty = os.path.realpath(tempfile.mkdtemp(prefix="bigblob-empty-"))
        self.addCleanup(shutil.rmtree, empty, True)
        subprocess.run(["git", "init", "-q"], cwd=empty, check=True,
                       capture_output=True)
        out = subprocess.run([sys.executable, SCRIPT, empty],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        self.assertIn("nothing to report", out.stdout)


if __name__ == "__main__":
    unittest.main()
