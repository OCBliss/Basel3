"""Independent acquisition, causal cleaning, provenance and consumer contracts."""

import copy
import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest import mock
from urllib.parse import parse_qs, urlsplit

import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

acquisition = importlib.import_module("src.RWA.data.yields.acquire")
hierarchy = importlib.import_module("src.RWA.models.parameter_hierarchy.workflow")


def csv_bytes(rows, header="observation_date,DGS1,DGS2"):
    return (header + "\n" + "\n".join(rows) + "\n").encode("utf-8")


SAMPLE = csv_bytes([
    "2010-01-04,4.0,.",
    "2010-01-05,4.1,5.1",
    "2010-01-06,.,5.2",
    "2010-01-07,4.3,",
    "2010-01-08,4.4,5.4",
    "2010-01-11,4.5,.",
])


class FakeResponse:
    """A requests-like byte stream, independent of the acquisition parser."""

    def __init__(self, payload=SAMPLE, status=200):
        self.content = payload
        self.text = payload.decode("utf-8", errors="replace")
        self.status_code = status
        self.headers = {"Content-Type": "text/csv", "Content-Length": str(len(payload))}
        self.url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("HTTP %s" % self.status_code, response=self)

    def iter_content(self, chunk_size=65536, **kwargs):
        for offset in range(0, len(self.content), chunk_size):
            yield self.content[offset:offset + chunk_size]

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class YieldParsingTests(unittest.TestCase):
    def parse(self, payload=SAMPLE, **overrides):
        settings = dict(maturities=(1, 2), start="2010-01-04", end="2010-01-12",
                        max_fill_days=7, max_age_days=7)
        settings.update(overrides)
        return acquisition.parse_yields(payload, **settings)

    def test_common_support_and_causal_fills_preserve_original_quotes(self):
        series, quality = self.parse()
        for tenor in (1, 2):
            days = ["2010-01-05", "2010-01-06", "2010-01-07", "2010-01-08"]
            if tenor == 1:
                days.insert(0, "2010-01-04")
            expected_dates = pd.to_datetime(days)
            self.assertEqual(list(series[tenor].columns),
                             ["observation_date", "DGS%d" % tenor, "yield_clean", "is_imputed", "source_date"])
            pd.testing.assert_index_equal(pd.DatetimeIndex(series[tenor].observation_date),
                                          expected_dates.rename("observation_date"))
        np.testing.assert_allclose(series[1].DGS1, [4., 4.1, np.nan, 4.3, 4.4], equal_nan=True)
        np.testing.assert_allclose(series[1].yield_clean, [4., 4.1, 4.1, 4.3, 4.4])
        self.assertEqual(series[1].is_imputed.tolist(), [False, False, True, False, False])
        self.assertEqual(series[1].source_date.tolist(),
                         pd.to_datetime(["2010-01-04", "2010-01-05", "2010-01-05", "2010-01-07", "2010-01-08"]).tolist())
        np.testing.assert_allclose(series[2].yield_clean, [5.1, 5.2, 5.2, 5.4])
        self.assertEqual(series[2].is_imputed.tolist(), [False, False, True, False])
        self.assertEqual(quality["common_start"], "2010-01-05")
        self.assertEqual(quality["common_end"], "2010-01-08")
        self.assertEqual(quality["rows"], 4)
        self.assertEqual(quality["series"]["DGS1"]["last_observed"], "2010-01-11")
        self.assertEqual(quality["series"]["DGS2"]["last_observed"], "2010-01-08")
        self.assertEqual(quality["series"]["DGS1"]["rows"], 5)
        self.assertEqual(quality["series"]["DGS1"]["filled_quotes"], 1)
        self.assertEqual(quality["series"]["DGS2"]["filled_quotes"], 1)
        self.assertEqual(quality["series"]["DGS1"]["leading_rows_excluded"], 0)
        self.assertEqual(quality["series"]["DGS2"]["leading_rows_excluded"], 1)
        self.assertEqual(quality["series"]["DGS1"]["trailing_rows_excluded"], 1)
        self.assertEqual(quality["series"]["DGS2"]["trailing_rows_excluded"], 1)
        self.assertEqual(quality["max_fill_days"], 7)
        self.assertEqual(quality["max_age_days"], 7)

    def test_common_start_can_use_an_earlier_genuine_source_without_backfilling(self):
        series, _ = self.parse(csv_bytes([
            "2010-01-04,4.0,.", "2010-01-05,.,5.1", "2010-01-06,4.2,5.2",
        ]), end="2010-01-06")
        first = series[1].loc[series[1].observation_date == pd.Timestamp("2010-01-05")].iloc[0]
        self.assertEqual(first.observation_date, pd.Timestamp("2010-01-05"))
        self.assertTrue(pd.isna(first.DGS1))
        self.assertEqual(first.yield_clean, 4.)
        self.assertEqual(first.source_date, pd.Timestamp("2010-01-04"))
        self.assertTrue(first.is_imputed)
        self.assertEqual(series[1].iloc[0].observation_date, pd.Timestamp("2010-01-04"))

    def test_server_bounds_are_applied_locally_and_cannot_seed_a_fill(self):
        series, _ = self.parse(csv_bytes([
            "2009-12-31,99.0,99.0", "2010-01-04,.,.",
            "2010-01-05,4.0,5.0", "2010-01-06,4.1,5.1",
            "2011-01-04,88.0,88.0",
        ]), end="2010-01-06")
        self.assertEqual(series[1].observation_date.tolist(),
                         pd.to_datetime(["2010-01-05", "2010-01-06"]).tolist())
        np.testing.assert_allclose(series[1].yield_clean, [4., 4.1])

    def test_future_quote_does_not_hide_stale_requested_history(self):
        with self.assertRaises(ValueError):
            self.parse(csv_bytes([
                "2010-01-04,4,5", "2010-01-05,4.1,5.1", "2011-01-04,4.2,5.2",
            ]), end="2010-01-20")

    def test_appending_future_observations_does_not_change_past_cleaned_values(self):
        short = csv_bytes(["2010-01-04,4,5", "2010-01-05,.,5.1", "2010-01-06,4.2,5.2"])
        long = short + b"2010-01-07,40,50\n2010-01-08,.,60\n2010-01-11,70,80\n"
        earlier, _ = self.parse(short, end="2010-01-06")
        later, _ = self.parse(long, end="2010-01-11")
        for tenor in (1, 2):
            past = later[tenor].loc[later[tenor].observation_date <= pd.Timestamp("2010-01-06")]
            pd.testing.assert_frame_equal(earlier[tenor].reset_index(drop=True), past.reset_index(drop=True))

    def test_input_order_does_not_change_dated_results(self):
        lines = SAMPLE.decode().splitlines()
        reverse = (lines[0] + "\n" + "\n".join(reversed(lines[1:])) + "\n").encode()
        ascending, _ = self.parse()
        descending, _ = self.parse(reverse)
        for tenor in (1, 2):
            pd.testing.assert_frame_equal(ascending[tenor], descending[tenor])

    def test_weekend_is_not_expanded_into_invented_rows(self):
        series, _ = self.parse(csv_bytes(["2010-01-08,4,5", "2010-01-11,4.1,5.1"]),
                               end="2010-01-11")
        self.assertEqual(series[1].observation_date.tolist(),
                         pd.to_datetime(["2010-01-08", "2010-01-11"]).tolist())

    def test_long_calendar_gap_is_rejected_even_when_both_quotes_are_real(self):
        with self.assertRaises(ValueError):
            self.parse(csv_bytes(["2010-01-04,4,5", "2010-01-20,4.1,5.1"]),
                       end="2010-01-20")

    def test_excessively_old_fill_is_rejected_even_with_recent_recovery(self):
        with self.assertRaises(ValueError):
            self.parse(csv_bytes([
                "2010-01-04,4,5", "2010-01-08,.,5.1", "2010-01-12,.,5.2", "2010-01-13,4.1,5.3",
            ]), end="2010-01-13")

    def test_staleness_uses_last_genuine_quote_for_each_tenor(self):
        with self.assertRaises(ValueError):
            self.parse(csv_bytes([
                "2010-01-04,4,5", "2010-01-08,4.1,.", "2010-01-11,4.2,.", "2010-01-12,4.3,.",
            ]), max_fill_days=30, end="2010-01-12", max_age_days=7)

    def test_invalid_tokens_cannot_be_silently_reclassified_as_missing(self):
        for value in ("oops", "NA", "NaN", "null", "inf", "-inf", "0", "-0.1",
                      "4\x00", "4\x01", "4\x1f"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.parse(csv_bytes(["2010-01-04,4,5", "2010-01-05,%s,5.1" % value]),
                           end="2010-01-05")

    def test_dates_must_be_unique_valid_iso_calendar_dates(self):
        for date in ("2010-01-04", "2010-02-30", "01/05/2010", "2010-1-5", "", "NaT"):
            with self.subTest(date=date), self.assertRaises(ValueError):
                self.parse(csv_bytes(["2010-01-04,4,5", "%s,4.1,5.1" % date]), end="2010-01-06")

    def test_malformed_headers_and_empty_payloads_fail(self):
        invalid = [b"", b"<html>rate limited</html>", b"observation_date,DGS1,DGS2\n",
                   csv_bytes(["2010-01-04,4,5"], header="date,DGS1,DGS2"),
                   csv_bytes(["2010-01-04,4,5"], header="observation_date,DGS1,DGS1"),
                   csv_bytes(["2010-01-04,4"], header="observation_date,DGS1"),
                   csv_bytes(["2010-01-04,4"]),
                   csv_bytes(["2010-01-04,4,5,unexpected"])]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.parse(payload, end="2010-01-04")

    def test_empty_series_and_disjoint_real_support_fail(self):
        for payload in [csv_bytes(["2010-01-04,4,.", "2010-01-05,4.1,."]),
                        csv_bytes(["2010-01-04,4,.", "2010-01-05,.,5"])]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.parse(payload, end="2010-01-05")

    def test_invalid_requested_dates_and_limits_fail(self):
        for settings in (dict(start="01/04/2010"), dict(end="2010-02-30"),
                         dict(start="2010-01-13"), dict(max_fill_days=-1),
                         dict(max_age_days=-1), dict(maturities=()), dict(maturities=(1, 1))):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                self.parse(**settings)


class YieldSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT/'tests')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.output = self.directory/'snapshot'
        self.session = mock.Mock()
        self.session.get.return_value = FakeResponse()

    def acquire(self, **overrides):
        settings = dict(output=self.output, start="2010-01-04", end="2010-01-12",
                        maturities=(1, 2), session=self.session)
        settings.update(overrides)
        return acquisition.acquire_snapshot(**settings)

    def test_snapshot_preserves_response_and_is_compatible_with_existing_reader(self):
        manifest = self.acquire()
        self.assertEqual((self.output/'raw/fred.csv').read_bytes(), SAMPLE)
        self.assertEqual(json.loads((self.output/'snapshot.json').read_text()), manifest)
        self.assertEqual(manifest['status'], 'complete')
        self.assertEqual(manifest['schema_version'], 1)
        self.assertEqual(manifest['raw']['path'], 'raw/fred.csv')
        self.assertEqual(manifest['raw']['sha256'], hashlib.sha256(SAMPLE).hexdigest())
        self.assertEqual(manifest['raw']['bytes'], len(SAMPLE))
        recorded_url = urlsplit(manifest['raw']['url'])
        self.assertEqual(recorded_url.scheme, 'https')
        self.assertEqual(recorded_url.netloc, 'fred.stlouisfed.org')
        self.assertEqual(recorded_url.path, '/graph/fredgraph.csv')
        self.assertEqual(parse_qs(recorded_url.query),
                         {'id': ['DGS1,DGS2'], 'cosd': ['2010-01-04'], 'coed': ['2010-01-12']})
        sources = {source['maturity']: source for source in manifest['sources']}
        self.assertEqual(set(sources), {1, 2})
        expected, _ = acquisition.parse_yields(SAMPLE, maturities=(1, 2),
                                              start="2010-01-04", end="2010-01-12")
        panel, _ = hierarchy.read_yield_panel(self.output/'series', [1, 2])
        for tenor in (1, 2):
            aligned = expected[tenor].set_index('observation_date').loc[panel.index]
            np.testing.assert_allclose(panel[tenor], aligned.yield_clean)
            saved = pd.read_csv(self.output/'series'/('DGS%d.csv' % tenor))
            np.testing.assert_allclose(saved['DGS%d' % tenor], expected[tenor]['DGS%d' % tenor], equal_nan=True)
            source = sources[tenor]
            self.assertEqual(source['series_id'], 'DGS%d' % tenor)
            self.assertEqual(source['path'], 'series/DGS%d.csv' % tenor)
            self.assertEqual(source['sha256'], hashlib.sha256((self.output/source['path']).read_bytes()).hexdigest())

    def test_export_retains_the_prior_quote_needed_to_fill_at_common_start(self):
        self.session.get.return_value = FakeResponse(csv_bytes([
            "2010-01-04,4.0,.", "2010-01-05,.,5.1", "2010-01-06,4.2,5.2",
        ]))
        self.acquire(end="2010-01-06")
        panel, _ = hierarchy.read_yield_panel(self.output/'series', [1, 2])
        self.assertEqual(panel.index.tolist(), pd.to_datetime(["2010-01-05", "2010-01-06"]).tolist())
        np.testing.assert_allclose(panel.to_numpy(), [[4., 5.1], [4.2, 5.2]])

    def test_request_uses_official_endpoint_date_bounds_and_a_bounded_timeout(self):
        self.acquire()
        self.session.get.assert_called_once()
        positional, keywords = self.session.get.call_args
        self.assertEqual(positional[0], 'https://fred.stlouisfed.org/graph/fredgraph.csv')
        self.assertEqual(keywords['params']['id'], 'DGS1,DGS2')
        self.assertEqual(keywords['params']['cosd'], '2010-01-04')
        self.assertEqual(keywords['params']['coed'], '2010-01-12')
        self.assertTrue(keywords['stream'])
        self.assertFalse(keywords['allow_redirects'])
        timeout = keywords['timeout']
        self.assertTrue(timeout)
        for bound in timeout if isinstance(timeout, tuple) else (timeout,):
            self.assertGreater(bound, 0)
            self.assertLessEqual(bound, 120)

    def test_transient_responses_are_retried_with_a_finite_attempt_budget(self):
        self.session.get.side_effect = [FakeResponse(status=429), FakeResponse(status=503), FakeResponse()]
        with mock.patch('time.sleep'):
            manifest = self.acquire()
        self.assertEqual(manifest['status'], 'complete')
        self.assertEqual(self.session.get.call_count, 3)

    def test_connection_timeout_is_retried_and_terminal_failure_creates_nothing(self):
        self.session.get.side_effect = requests.Timeout('fixture timeout')
        with mock.patch('time.sleep'), self.assertRaises((ValueError, requests.RequestException, RuntimeError)):
            self.acquire()
        self.assertEqual(self.session.get.call_count, 3)
        self.assertFalse(self.output.exists())

    def test_interrupted_body_retries_from_the_start_without_duplicate_bytes(self):
        class InterruptedResponse(FakeResponse):
            def iter_content(self, chunk_size=65536, **kwargs):
                yield self.content[:30]
                raise requests.exceptions.ChunkedEncodingError('fixture interrupted response')

        interrupted = InterruptedResponse()
        completed = FakeResponse()
        self.session.get.side_effect = [interrupted, completed]
        with mock.patch('time.sleep'):
            self.acquire()
        self.assertEqual(self.session.get.call_count, 2)
        self.assertEqual((self.output/'raw/fred.csv').read_bytes(), SAMPLE)
        self.assertTrue(interrupted.closed)
        self.assertTrue(completed.closed)

    def test_permanent_http_failure_and_redirect_are_not_retried(self):
        for status in (404, 302):
            self.session.get.reset_mock()
            self.session.get.return_value = FakeResponse(status=status)
            with self.subTest(status=status), mock.patch('time.sleep'), \
                    self.assertRaises((ValueError, requests.RequestException, RuntimeError)):
                self.acquire()
            self.session.get.assert_called_once()
            self.assertFalse(self.output.exists())

    def test_oversized_body_is_rejected_even_without_content_length(self):
        response = FakeResponse(b'x' * (8 * 1024 * 1024 + 1))
        response.headers.pop('Content-Length')
        self.session.get.return_value = response
        with self.assertRaises((ValueError, RuntimeError)):
            self.acquire()
        self.assertFalse(self.output.exists())

    def test_publication_failure_removes_the_reserved_incomplete_snapshot(self):
        original_write_text = Path.write_text

        def fail_manifest(path, *args, **kwargs):
            if path.name == 'snapshot.json':
                raise OSError('simulated manifest publication failure')
            return original_write_text(path, *args, **kwargs)

        with mock.patch.object(Path, 'write_text', fail_manifest), self.assertRaises(OSError):
            self.acquire()
        self.assertFalse(self.output.exists())

    def test_invalid_response_never_publishes_a_complete_snapshot_or_reserves_output(self):
        self.session.get.return_value = FakeResponse(csv_bytes(["2010-01-04,4,broken"]))
        with self.assertRaises(ValueError):
            self.acquire()
        self.assertFalse(self.output.exists())

    def test_existing_output_is_preserved_without_network_request(self):
        self.output.mkdir()
        previous = self.output/'snapshot.json'
        previous.write_text('{"status":"complete","sentinel":"preserve me"}\n')
        before = previous.read_bytes()
        with self.assertRaises((FileExistsError, ValueError)):
            self.acquire()
        self.assertEqual(previous.read_bytes(), before)
        self.session.get.assert_not_called()

    def test_external_output_and_symlink_escape_are_rejected_before_fetch(self):
        escape = self.directory/'escape'
        escape.symlink_to(ROOT.parent, target_is_directory=True)
        for target in (ROOT.parent/'forbidden-rwa-snapshot', escape/'forbidden-rwa-snapshot'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.acquire(output=target)
        self.session.get.assert_not_called()

    def test_verified_provenance_identifies_the_exact_snapshot_manifest(self):
        manifest = self.acquire()
        path = self.output/'snapshot.json'
        verified = acquisition.verify_snapshot(path, self.output/'series', (1, 2))
        self.assertEqual(verified['path'], str(path.relative_to(ROOT)))
        self.assertEqual(verified['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(verified['quality'], manifest['quality'])
        self.assertEqual(verified['requested_end'], '2010-01-12')

    def test_verification_rejects_changed_processed_or_raw_bytes(self):
        self.acquire()
        for relative in ('series/DGS1.csv', 'series/DGS2.csv', 'raw/fred.csv'):
            path = self.output/relative
            previous = path.read_bytes()
            path.write_bytes(previous + b'\n')
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                acquisition.verify_snapshot(self.output/'snapshot.json', self.output/'series', (1, 2))
            path.write_bytes(previous)

    def test_updated_source_hash_cannot_disguise_a_change_from_raw_quotes(self):
        manifest = self.acquire()
        path = self.output/'series/DGS1.csv'
        frame = pd.read_csv(path)
        frame.loc[0, ['DGS1', 'yield_clean']] += .05
        frame.to_csv(path, index=False, float_format='%.17g')
        manifest['sources'][0]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.output/'snapshot.json').write_text(json.dumps(manifest))
        with self.assertRaises(ValueError):
            acquisition.verify_snapshot(self.output/'snapshot.json', self.output/'series', (1, 2))

    def test_manifest_quality_must_match_the_preserved_raw_observations(self):
        original = self.acquire()
        path = self.output/'snapshot.json'
        for field, value in [('rows', 999), ('common_end', '2010-01-12')]:
            manifest = copy.deepcopy(original)
            manifest['quality'][field] = value
            path.write_text(json.dumps(manifest))
            with self.subTest(field=field), self.assertRaises(ValueError):
                acquisition.verify_snapshot(path, self.output/'series', (1, 2))

    def test_verification_requires_the_snapshot_own_input_directory(self):
        self.acquire()
        with self.assertRaises(ValueError):
            acquisition.verify_snapshot(self.output/'snapshot.json', self.directory/'other-series', (1, 2))

    def test_verification_rejects_incomplete_or_unsupported_manifests(self):
        original = self.acquire()
        path = self.output/'snapshot.json'
        for field, value in [('status', 'incomplete'), ('status', None),
                             ('schema_version', 0), ('schema_version', 2), ('schema_version', True)]:
            manifest = copy.deepcopy(original)
            manifest[field] = value
            path.write_text(json.dumps(manifest))
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                acquisition.verify_snapshot(path, self.output/'series', (1, 2))

    def test_verification_rejects_duplicate_or_missing_maturity_contracts(self):
        original = self.acquire()
        path = self.output/'snapshot.json'
        examples = []
        duplicate = copy.deepcopy(original)
        duplicate['maturities'] = [1, 1]
        duplicate['sources'] = [original['sources'][0], original['sources'][0]]
        examples.append(('duplicates', duplicate, (1,)))
        missing_source = copy.deepcopy(original)
        missing_source['sources'] = missing_source['sources'][:1]
        examples.append(('missing source', missing_source, (1, 2)))
        missing_tenor = copy.deepcopy(original)
        missing_tenor['maturities'] = [1]
        examples.append(('missing maturity', missing_tenor, (1, 2)))
        missing_list = copy.deepcopy(original)
        del missing_list['maturities']
        examples.append(('absent maturity list', missing_list, (1, 2)))
        for label, manifest, requested in examples:
            path.write_text(json.dumps(manifest))
            with self.subTest(case=label), self.assertRaises(ValueError):
                acquisition.verify_snapshot(path, self.output/'series', requested)
        path.write_text(json.dumps(original))
        for requested in ((1, 3), (1, 1), (True,), ()):
            with self.subTest(requested=requested), self.assertRaises(ValueError):
                acquisition.verify_snapshot(path, self.output/'series', requested)

    def test_verification_rejects_manifest_source_path_traversal(self):
        original = self.acquire()
        path = self.output/'snapshot.json'
        for location in ('sources', 'raw'):
            manifest = copy.deepcopy(original)
            if location == 'sources':
                manifest['sources'][0]['path'] = '../outside.csv'
            else:
                manifest['raw']['path'] = '../outside.csv'
            path.write_text(json.dumps(manifest))
            with self.subTest(location=location), self.assertRaises(ValueError):
                acquisition.verify_snapshot(path, self.output/'series', (1, 2))

    def test_verification_rejects_a_series_symlink_outside_the_repository(self):
        self.acquire()
        path = self.output/'series/DGS1.csv'
        path.unlink()
        path.symlink_to(ROOT.parent/'forbidden-snapshot-source.csv')
        with self.assertRaises(ValueError):
            acquisition.verify_snapshot(self.output/'snapshot.json', self.output/'series', (1, 2))

    def test_serial_command_preserves_verified_snapshot_and_rejects_later_tampering(self):
        rng = np.random.default_rng(417)
        dates = pd.bdate_range('2010-01-04', periods=96)
        means = np.array([3., 4.])
        values = np.empty((len(dates), 2))
        values[0] = means
        for position in range(1, len(dates)):
            previous = values[position-1]
            values[position] = previous + 8*(means-previous)/252 + .4*np.sqrt(previous/252)*rng.normal(size=2)
        payload = csv_bytes(['%s,%.15g,%.15g' % (day.date().isoformat(), row[0], row[1])
                             for day, row in zip(dates, values)])
        self.session.get.return_value = FakeResponse(payload)
        snapshot = self.acquire(end=dates[-1].date().isoformat())
        manifest_path = self.output/'snapshot.json'
        expected_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        result_directory = self.directory/'model-results'
        command = ['--input', str(self.output/'series'), '--input-manifest', str(manifest_path),
                   '--output', str(result_directory), '--maturities', '1', '2',
                   '--yield-window', '32', '--parameter-window', '16',
                   '--history-window', '12', '--years', '1']
        with mock.patch.object(hierarchy, 'run_years', return_value=[{'year': 1}]) as run, \
                redirect_stdout(StringIO()):
            hierarchy.main(command)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[1].shape, (12,3,2))
        np.testing.assert_allclose(run.call_args.args[1][:,0], values[-12:], rtol=1e-14)
        model = json.loads((result_directory/'manifest.json').read_text())
        self.assertEqual(model['yield_acquisition']['sha256'], expected_sha)
        self.assertEqual(model['yield_acquisition']['quality'], snapshot['quality'])
        self.assertEqual(model['forecast_origin'], dates[-1].date().isoformat())
        self.assertEqual(model['schema_version'], 2)
        self.assertEqual(model['state_names'], ['rate', 'sigma', 'xi'])
        self.assertEqual(model['walk_history_rows'], 12)
        self.assertEqual(run.call_args.args[3:7], (1,252,1/252,1))
        self.assertEqual(model['units'], 'FRED percentage points for rates')

        # The CLI must check acquisition integrity before it can publish another
        # model result; a successful old result remains intact after rejection.
        previous_manifest = (result_directory/'manifest.json').read_bytes()
        changed = self.output/'series/DGS1.csv'
        changed.write_bytes(changed.read_bytes() + b'\n')
        rejected_output = self.directory/'tampered-model-results'
        command[command.index('--output') + 1] = str(rejected_output)
        with self.assertRaises(SystemExit) as rejected, mock.patch('sys.stderr', new_callable=StringIO) as error:
            hierarchy.main(command)
        self.assertEqual(rejected.exception.code, 2)
        self.assertIn('hash', error.getvalue().lower())
        self.assertFalse(rejected_output.exists())
        self.assertEqual((result_directory/'manifest.json').read_bytes(), previous_manifest)


if __name__ == '__main__':
    unittest.main()
