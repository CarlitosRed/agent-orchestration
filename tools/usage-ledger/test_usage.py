"""Tests for the usage ledger. Offline, throw-away temp folders only.

Run:  python -m unittest discover -s tools/usage-ledger -p "test_usage.py" -v
"""
import datetime
import io
import os
import shutil
import tempfile
import unittest

import usage as U


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="usage-test-")
        self.path = os.path.join(self.dir, "usage.json")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = U.main([argv[0], self.path, *argv[1:]], out=out, err=err)
        return code, out.getvalue(), err.getvalue()

    def ok(self, *argv):
        code, out, err = self.run_cli(*argv)
        self.assertEqual(code, 0, f"{argv[0]} failed: {err}")
        return out

    def refused(self, *argv):
        code, out, err = self.run_cli(*argv)
        self.assertEqual(code, 1, f"expected refusal, got {code}: {out}{err}")
        self.assertIn("REFUSED", err)
        return err

    def init(self):
        self.ok("init")

    def log(self, vendor="Claude", role="Build Engineer", task="task-1", cost=None, when=None):
        args = ["log", "--vendor", vendor, "--role", role, "--task", task]
        if cost is not None:
            args += ["--cost", str(cost)]
        if when is not None:
            args += ["--when", when]
        return self.run_cli(*args)

    def ago(self, **kwargs):
        return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(**kwargs)).isoformat()


class WindowParsingTests(unittest.TestCase):
    def test_hours_and_days_parse(self):
        self.assertEqual(U.parse_window("5h"), datetime.timedelta(hours=5))
        self.assertEqual(U.parse_window("7d"), datetime.timedelta(days=7))

    def test_bad_window_is_an_error(self):
        for bad in ("5", "h5", "5w", "", "5 h", "-5h"):
            with self.assertRaises(U.Broken):
                U.parse_window(bad)


class InitAndLogTests(Base):
    def test_init_twice_refused(self):
        self.init()
        self.refused("init")

    def test_log_defaults_cost_to_one(self):
        self.init()
        code, out, err = self.log()
        self.assertEqual(code, 0, err)
        data = U.load(self.path)
        self.assertEqual(data["entries"][0]["cost"], 1)

    def test_log_accepts_a_real_cost(self):
        self.init()
        code, out, err = self.log(cost=22099)
        self.assertEqual(code, 0, err)
        data = U.load(self.path)
        self.assertEqual(data["entries"][0]["cost"], 22099)

    def test_log_refuses_non_positive_cost(self):
        self.init()
        code, out, err = self.log(cost=0)
        self.assertEqual(code, 2, out + err)
        code, out, err = self.log(cost=-5)
        self.assertEqual(code, 2, out + err)

    def test_log_refuses_bad_when(self):
        self.init()
        code, out, err = self.log(when="not-a-date")
        self.assertEqual(code, 2, out + err)
        self.assertIn("ISO 8601", err)

    def test_log_accepts_an_explicit_when(self):
        self.init()
        code, out, err = self.log(when=self.ago(hours=1))
        self.assertEqual(code, 0, err)


class WindowTotalTests(Base):
    def test_status_sums_within_window_only(self):
        self.init()
        self.log(cost=1, when=self.ago(hours=1))
        self.log(cost=2, when=self.ago(hours=10))  # outside a 5h window
        out = self.ok("status", "--window", "5h")
        self.assertIn(": 1", out)

    def test_status_defaults_to_all_vendors(self):
        self.init()
        self.log(vendor="Claude", cost=1, when=self.ago(hours=1))
        self.log(vendor="Codex", cost=2, when=self.ago(hours=1))
        out = self.ok("status", "--window", "5h")
        self.assertIn(": 3", out)

    def test_status_scoped_to_one_vendor(self):
        self.init()
        self.log(vendor="Claude", cost=1, when=self.ago(hours=1))
        self.log(vendor="Codex", cost=2, when=self.ago(hours=1))
        out = self.ok("status", "--window", "5h", "--vendor", "Codex")
        self.assertIn(": 2", out)

    def test_a_resume_is_just_another_log_entry(self):
        # R14: "a resumed helper counts as a launch" - the tool has no concept of resume, it only sums what
        # is logged, so the caller logging a resume as its own entry is what makes this true.
        self.init()
        self.log(cost=1, when=self.ago(hours=1))
        self.log(cost=1, when=self.ago(minutes=30))  # the "resume"
        out = self.ok("status", "--window", "5h")
        self.assertIn(": 2", out)

    def test_seven_day_window(self):
        self.init()
        self.log(cost=5, when=self.ago(days=6))
        self.log(cost=5, when=self.ago(days=8))  # outside a 7d window
        out = self.ok("status", "--window", "7d")
        self.assertIn(": 5", out)


class CheckTests(Base):
    def test_check_passes_under_ceiling(self):
        self.init()
        self.log(cost=2, when=self.ago(hours=1))
        self.ok("check", "--window", "5h", "--ceiling", "5")

    def test_check_refuses_at_or_over_ceiling(self):
        self.init()
        self.log(cost=5, when=self.ago(hours=1))
        err = self.refused("check", "--window", "5h", "--ceiling", "5")
        self.assertIn("5", err)
        self.assertIn("queue", err)

    def test_check_does_not_write_anything(self):
        self.init()
        self.log(cost=5, when=self.ago(hours=1))
        before = U.load(self.path)
        self.run_cli("check", "--window", "5h", "--ceiling", "5")
        after = U.load(self.path)
        self.assertEqual(before, after)

    def test_check_scoped_to_one_vendor_ignores_others(self):
        self.init()
        self.log(vendor="Codex", cost=10, when=self.ago(hours=1))
        self.ok("check", "--window", "5h", "--ceiling", "5", "--vendor", "Claude")


if __name__ == "__main__":
    unittest.main()
