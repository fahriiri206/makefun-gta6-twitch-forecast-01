import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main  # noqa: E402
import model  # noqa: E402

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]


def iso(hours_from_day=0):
    # 2026-11-19T00:00:00Z plus whole hours, stdlib only
    import datetime
    base = datetime.datetime(2026, 11, 19, tzinfo=datetime.timezone.utc)
    return (base + datetime.timedelta(hours=hours_from_day)).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_day(day_start, hours):
    import datetime
    base = datetime.datetime.fromisoformat(day_start.replace("Z", "+00:00"))
    return (base + datetime.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_comp(name, curve, platforms="PS5", unlock="Midnight local rolling", day_start="2020-01-01T00:00:00Z"):
    hourly = [{"from": iso_day(day_start, h), "viewers": v, "channels": 1} for h, v in enumerate(curve)]
    return {
        "name": name,
        "day_start": day_start,
        "unlock": unlock,
        "platforms": platforms,
        "source": "synthetic test",
        "hourly": hourly,
    }


def make_case(p1=1000, comparables=None, history_hourly=None, known=None, case_id="p00"):
    forecast = []
    for h in range(2, 25):
        forecast.append({"hour": h, "from": iso(h - 1), "until": iso(h)})
    if known is None:
        known = [{"hour": 1, "from": iso(0), "until": iso(1), "viewers": p1, "channels": 10, "reads": 60}]
    return {
        "schema": "makefun/twitch-ccu-case/v1",
        "id": case_id,
        "game": {"name": "Synthetic", "twitch_id": "1"},
        "day_start": iso(0),
        "checkpoint": iso(1),
        "levels": LEVELS,
        "known": known,
        "forecast": forecast,
        "history": [],
        "history_hourly": history_hourly or [],
        "streams": None,
        "categories_hourly": None,
        "comparables": comparables or [],
        "notes": "synthetic",
    }


def assert_valid_forecast(test, forecast):
    test.assertEqual(set(forecast), {"hours"})
    rows = forecast["hours"]
    test.assertEqual(len(rows), 23)
    test.assertEqual([r["hour"] for r in rows], list(range(2, 25)))
    for row in rows:
        test.assertEqual(set(row), {"hour", "q"})
        q = row["q"]
        test.assertEqual(len(q), 5)
        for value in q:
            test.assertTrue(isinstance(value, (int, float)))
            test.assertTrue(math.isfinite(value))
            test.assertGreater(value, 0)
            test.assertLessEqual(value, 1_000_000_000)
        test.assertEqual(q, sorted(q))


class ContractTests(unittest.TestCase):
    def test_exact_contract_and_ordering(self):
        forecast = model.forecast_case(make_case(), "p00.in")
        assert_valid_forecast(self, forecast)

    def test_zero_counts_and_missing_optionals(self):
        curve = [0] * 24
        case = make_case(p1=0, comparables=[make_comp("zero", curve)])
        assert_valid_forecast(self, model.forecast_case(case, "p00.in"))

    def test_missing_known_falls_back_to_positive_values(self):
        case = make_case(known=[])
        assert_valid_forecast(self, model.forecast_case(case, "p00.in"))

    def test_future_history_rows_are_ignored(self):
        base_history = [
            {"from": iso(-2), "viewers": 500, "channels": 5, "reads": 60},
            {"from": iso(-1), "viewers": 700, "channels": 6, "reads": 60},
        ]
        future = base_history + [
            {"from": iso(4), "viewers": 9_999_999, "channels": 99, "reads": 60},
            {"from": iso(12), "viewers": 50_000_000, "channels": 99, "reads": 60},
        ]
        a = model.forecast_case(make_case(p1=1000, history_hourly=base_history), "a.in")
        b = model.forecast_case(make_case(p1=1000, history_hourly=future), "b.in")
        self.assertEqual(a, b)

    def test_comparables_change_the_forecast(self):
        rising = [1000 * (1.1 ** h) for h in range(24)]
        falling = [1000 * (0.9 ** h) for h in range(24)]
        a = model.forecast_case(make_case(comparables=[make_comp("rise", rising)]), "a.in")
        b = model.forecast_case(make_case(comparables=[make_comp("fall", falling)]), "b.in")
        self.assertNotEqual(a, b)

    def test_single_comparable_keeps_an_honest_spread(self):
        curve = [1000 * (1.1 ** h) for h in range(24)]
        forecast = model.forecast_case(make_case(comparables=[make_comp("only", curve)]), "x.in")
        q = forecast["hours"][0]["q"]
        self.assertLess(q[0], q[2])
        self.assertGreater(q[4], q[2])

    def test_no_hardcoded_answer_when_comparables_are_absent(self):
        # With no analogues the model must still produce the same contract,
        # using the documented persistence fallback.
        forecast = model.forecast_case(make_case(p1=1234, comparables=[]), "p00.in")
        assert_valid_forecast(self, forecast)
        self.assertAlmostEqual(forecast["hours"][0]["q"][2], 1234, places=2)


class RunnerTests(unittest.TestCase):
    def run_case(self, name, payload, out_dir):
        in_dir = Path(out_dir) / "in"
        out_dir = Path(out_dir) / "out"
        in_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        (in_dir / name).write_text(json.dumps(payload), encoding="utf-8")
        old_in, old_out = os.environ.get("MAKEFUN_INPUT_DIR"), os.environ.get("MAKEFUN_OUTPUT_DIR")
        os.environ["MAKEFUN_INPUT_DIR"] = str(in_dir)
        os.environ["MAKEFUN_OUTPUT_DIR"] = str(out_dir)
        try:
            main.main()
        finally:
            if old_in is None:
                os.environ.pop("MAKEFUN_INPUT_DIR", None)
            else:
                os.environ["MAKEFUN_INPUT_DIR"] = old_in
            if old_out is None:
                os.environ.pop("MAKEFUN_OUTPUT_DIR", None)
            else:
                os.environ["MAKEFUN_OUTPUT_DIR"] = old_out
        return out_dir

    def test_filename_follows_input_stem_not_id_and_cases_are_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = self.run_case("weird.in", make_case(p1=111, case_id="p00"), tmp)
            self.assertTrue((out / "weird.out").is_file())
            self.assertFalse((out / "p00.out").exists())
            payload = json.loads((out / "weird.out").read_text())
            assert_valid_forecast(self, payload)

    def test_two_runs_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            payload = make_case(p1=250_000)
            oa = self.run_case("p00.in", payload, a)
            ob = self.run_case("p00.in", payload, b)
            self.assertEqual((oa / "p00.out").read_bytes(), (ob / "p00.out").read_bytes())

    def test_malformed_json_still_writes_valid_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            in_dir = Path(tmp) / "in"
            out_dir = Path(tmp) / "out"
            in_dir.mkdir()
            out_dir.mkdir()
            (in_dir / "broken.in").write_text("{not json", encoding="utf-8")
            old_in, old_out = os.environ.get("MAKEFUN_INPUT_DIR"), os.environ.get("MAKEFUN_OUTPUT_DIR")
            os.environ["MAKEFUN_INPUT_DIR"] = str(in_dir)
            os.environ["MAKEFUN_OUTPUT_DIR"] = str(out_dir)
            try:
                main.main()
            finally:
                os.environ["MAKEFUN_INPUT_DIR"] = old_in or ""
                os.environ["MAKEFUN_OUTPUT_DIR"] = old_out or ""
                os.environ.pop("MAKEFUN_INPUT_DIR", None) if old_in is None else None
                os.environ.pop("MAKEFUN_OUTPUT_DIR", None) if old_out is None else None
            data = (out_dir / "broken.out").read_text()
            self.assertLessEqual(len(data.encode()), 65536)
            assert_valid_forecast(self, json.loads(data))


if __name__ == "__main__":
    unittest.main()
