"""Exercise FFIEC quarter planning, archive validation, and resumable preparation."""

from datetime import date
import importlib.util
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

import yaml


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "src/call reports/prepare_call_reports.py"
SPEC = importlib.util.spec_from_file_location("ffiec_preparation_test", MODULE_PATH)
preparation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = preparation
SPEC.loader.exec_module(preparation)
QUARTER = date(2024, 3, 31)


def quarter_files(quarter=QUARTER):
    stamp = quarter.strftime("%m%d%Y")
    return {
        f"FFIEC CDR Call Bulk POR {stamp}.txt":
            b"IDRSSD\tFDIC Certificate Number\n101\t10\n202\t20\n",
        f"FFIEC CDR Call Schedule ENT {stamp}.txt":
            ("IDRSSD\tRCON9999\n\tREPORT DATE\n101\t{0}\n202\t{0}\n"
             .format(quarter.strftime("%Y%m%d"))).encode(),
        f"FFIEC CDR Call Schedule RC {stamp}.txt":
            b"IDRSSD\tRCON2170\n\tTOTAL ASSETS\n101\t100\n202\t200\n",
    }


def archive_bytes(files=None):
    if files is None:
        files = quarter_files()
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, contents in files.items():
            archive.writestr(name, contents)
    return result.getvalue()


class DownloadClient:
    def __init__(self, payload=None):
        self.payload = archive_bytes() if payload is None else payload
        self.calls = []

    def download(self, quarter, destination):
        self.calls.append((quarter, Path(destination)))
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        Path(destination).write_bytes(self.payload)


class FfiecPlanningTests(unittest.TestCase):
    def test_quarter_ends_include_boundaries_and_exclude_partial_quarters(self):
        self.assertEqual(preparation.quarter_ends(date(2023, 12, 31), date(2024, 6, 30)),
                         [date(2023, 12, 31), date(2024, 3, 31), date(2024, 6, 30)])
        self.assertEqual(preparation.quarter_ends(date(2024, 1, 1), date(2024, 3, 30)), [])
        self.assertEqual(preparation.quarter_ends(date(2024, 2, 29), date(2024, 4, 1)),
                         [date(2024, 3, 31)])

    def test_actual_yaml_requires_44_event_quarters_and_three_earlier_quarters(self):
        plan = preparation.plan_quarters(ROOT / "pipeline/pipeline_config_dynamic.yaml")
        self.assertEqual(len(plan["event_quarters"]), 44)
        self.assertEqual(plan["event_quarters"][0], "20140331")
        self.assertEqual(plan["event_quarters"][-1], "20241231")
        self.assertEqual(plan["history_quarters"], ["20130630", "20130930", "20131231"])
        self.assertEqual(plan["required_quarters"],
                         plan["history_quarters"] + plan["event_quarters"])
        self.assertEqual(len(plan["required_quarters"]), 47)

    def test_different_yaml_ranges_are_unioned_with_each_quarters_history(self):
        source = yaml.safe_load((ROOT / "pipeline/pipeline_config_dynamic.yaml").read_text())
        ranges = {
            "6.0.1": ("2020-04-01", "2020-06-30"),
            "6.0.2": ("2021-01-01", "2021-03-31"),
            "6.0.3": ("2020-04-01", "2020-06-30"),
        }
        for step, (start, end) in ranges.items():
            arguments = source["scripts"][step]["args"]
            arguments[arguments.index("--start-date") + 1] = start
            arguments[arguments.index("--end-date") + 1] = end
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "pipeline.yaml"
            config.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
            plan = preparation.plan_quarters(config)
            self.assertEqual(plan["event_quarters"], ["20200630", "20210331"])
            self.assertEqual(plan["history_quarters"],
                             ["20190930", "20191231", "20200331", "20200930", "20201231"])
            self.assertEqual(plan["required_quarters"],
                             ["20190930", "20191231", "20200331", "20200630",
                              "20200930", "20201231", "20210331"])
            no_history = preparation.plan_quarters(config, history_quarters=0)
            self.assertEqual(no_history["required_quarters"], ["20200630", "20210331"])


class FfiecArchiveTests(unittest.TestCase):
    def assert_invalid_archive(self, payload):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "quarter.zip"
            filename.write_bytes(payload)
            with self.assertRaises(preparation.PreparationError):
                preparation.validate_archive(filename, QUARTER)

    def test_accepts_flat_and_single_folder_archives(self):
        for prefix in ("", "FFIEC CDR Call Bulk All Schedules 20240331/"):
            with self.subTest(prefix=prefix), tempfile.TemporaryDirectory() as directory:
                contents = {prefix + name: value for name, value in quarter_files().items()}
                filename = Path(directory) / "quarter.zip"
                filename.write_bytes(archive_bytes(contents))
                members = preparation.validate_archive(filename, QUARTER)
                self.assertEqual({Path(member.filename).name for member in members},
                                 set(quarter_files()))

    def test_rejects_missing_por_ent_or_rc(self):
        for missing in quarter_files():
            with self.subTest(missing=missing):
                contents = quarter_files()
                del contents[missing]
                self.assert_invalid_archive(archive_bytes(contents))

    def test_rejects_empty_or_header_only_required_members_before_publication(self):
        for name, value in quarter_files().items():
            header_lines = 1 if "Bulk POR" in name else 2
            header_only = b"".join(value.splitlines(keepends=True)[:header_lines])
            for invalid in (b"", header_only):
                with self.subTest(file=name, bytes=len(invalid)):
                    contents = quarter_files()
                    contents[name] = invalid
                    payload = archive_bytes(contents)
                    self.assert_invalid_archive(payload)
                    with tempfile.TemporaryDirectory() as directory:
                        root = Path(directory)
                        with self.assertRaises(preparation.PreparationError):
                            preparation.prepare_quarter(QUARTER, root / "TXT", root / "cache",
                                                        DownloadClient(payload))
                        self.assertFalse((root / "cache/quarters/20240331.json").exists())
                        self.assertFalse((root / "TXT/FFIEC CDR Call Bulk All Schedules 20240331").exists())

    def test_rejects_wrong_quarter_and_non_txt_payloads(self):
        self.assert_invalid_archive(archive_bytes(quarter_files(date(2024, 6, 30))))
        contents = quarter_files()
        contents["unexpected.csv"] = b"IDRSSD,RCON2170\n101,100\n"
        self.assert_invalid_archive(archive_bytes(contents))

    def test_rejects_path_traversal_symlinks_and_duplicate_basenames(self):
        for unsafe_name in ("../escape.txt", "/escape.txt", "..\\escape.txt"):
            with self.subTest(name=unsafe_name):
                contents = quarter_files()
                contents[unsafe_name] = b"unsafe"
                self.assert_invalid_archive(archive_bytes(contents))
        contents = quarter_files()
        filename = next(iter(contents))
        contents["nested/" + filename] = contents[filename]
        self.assert_invalid_archive(archive_bytes(contents))
        payload = io.BytesIO(archive_bytes())
        with zipfile.ZipFile(payload, "a") as archive:
            symlink = zipfile.ZipInfo("linked.txt")
            symlink.create_system = 3
            symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(symlink, "../outside.txt")
        self.assert_invalid_archive(payload.getvalue())

    def test_rejects_incomplete_split_schedule_and_accepts_complete_parts(self):
        contents = quarter_files()
        contents["FFIEC CDR Call Schedule RCB 03312024(1 of 2).txt"] = b"IDRSSD\tRCFD0211\n101\t10\n"
        self.assert_invalid_archive(archive_bytes(contents))
        contents["FFIEC CDR Call Schedule RCB 03312024(2 of 2).txt"] = b"IDRSSD\tRCONG353\n101\t20\n"
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "quarter.zip"
            filename.write_bytes(archive_bytes(contents))
            self.assertEqual(len(preparation.validate_archive(filename, QUARTER)), 5)

    def test_rejects_html_truncated_archives_and_bad_crc(self):
        self.assert_invalid_archive(b"<!doctype html><html>Service unavailable</html>")
        payload = archive_bytes()
        self.assert_invalid_archive(payload[:-22])
        corrupted = payload.replace(b"IDRSSD", b"XDRSSD", 1)
        self.assertNotEqual(corrupted, payload)
        self.assert_invalid_archive(corrupted)

    def test_compressed_stream_corruption_raises_preparation_error(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, value in quarter_files().items():
                archive.writestr(name, value)
        payload = bytearray(stream.getvalue())
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            member = archive.infolist()[0]
            data_start = member.header_offset + 30 + len(member.filename.encode()) + len(member.extra)
        payload[data_start] = 0xff  # Invalid DEFLATE block; central directory stays readable.
        self.assert_invalid_archive(payload)


class FfiecPreparationTests(unittest.TestCase):
    def test_invalid_new_plan_removes_stale_manifest_except_in_plan_mode(self):
        source = yaml.safe_load((ROOT / "pipeline/pipeline_config_dynamic.yaml").read_text())
        arguments = source["scripts"]["6.0.1"]["args"]
        arguments[arguments.index("--start-date") + 1] = "not-a-date"
        for plan_only in (False, True):
            with self.subTest(plan_only=plan_only), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                config = root / "alternate.yaml"
                config.write_text(yaml.safe_dump(source))
                manifest = root / "prepared.json"
                previous = b'{"config":"previous.yaml","required_quarters":["20240331"]}\n'
                manifest.write_bytes(previous)
                args = ["--config", str(config), "--txt-dir", str(root / "TXT"),
                        "--cache-dir", str(root / "cache"), "--manifest", str(manifest)]
                if plan_only:
                    args.append("--plan")
                with mock.patch.object(preparation, "FFIECBulkClient") as client:
                    with mock.patch("builtins.print"):
                        self.assertEqual(preparation.main(args), 1)
                    client.assert_not_called()
                self.assertEqual(manifest.exists(), plan_only)
                if plan_only:
                    self.assertEqual(manifest.read_bytes(), previous)
                self.assertFalse((root / "TXT").exists())
                self.assertFalse((root / "cache").exists())

    def test_successful_plan_preserves_existing_manifest_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "prepared.json"
            previous = b'{"config":"previous.yaml"}\n'
            manifest.write_bytes(previous)
            with mock.patch.object(preparation, "FFIECBulkClient") as client:
                with mock.patch("builtins.print"):
                    result = preparation.main([
                        "--config", str(ROOT / "pipeline/pipeline_config_dynamic.yaml"),
                        "--txt-dir", str(root / "TXT"), "--cache-dir", str(root / "cache"),
                        "--manifest", str(manifest), "--plan",
                    ])
                client.assert_not_called()
            self.assertEqual(result, 0)
            self.assertEqual(manifest.read_bytes(), previous)
            self.assertEqual(list(root.iterdir()), [manifest])

    def test_first_run_then_cached_rerun_and_repair_of_missing_or_modified_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            txt_dir, cache_dir = root / "TXT", root / "cache"
            client = DownloadClient()
            result = preparation.prepare_quarter(QUARTER, txt_dir, cache_dir, client)
            target = txt_dir / "FFIEC CDR Call Bulk All Schedules 20240331"
            self.assertEqual(result["quarter"], "20240331")
            self.assertEqual(Path(result["directory"]), target)
            self.assertEqual(Path(result["archive"]), cache_dir / "archives/20240331.zip")
            self.assertEqual(len(result["files"]), 3)
            self.assertEqual(len(client.calls), 1)
            manifest = cache_dir / "quarters/20240331.json"
            self.assertTrue(manifest.is_file())
            json.loads(manifest.read_text())
            for name, contents in quarter_files().items():
                self.assertEqual((target / name).read_bytes(), contents)
            preparation.prepare_quarter(QUARTER, txt_dir, cache_dir, client)
            self.assertEqual(len(client.calls), 1)

            rc_name = "FFIEC CDR Call Schedule RC 03312024.txt"
            (target / rc_name).unlink()
            preparation.prepare_quarter(QUARTER, txt_dir, cache_dir, client)
            self.assertEqual((target / rc_name).read_bytes(), quarter_files()[rc_name])
            self.assertEqual(len(client.calls), 1)

            # Same-length corruption defeats a size-only completion check.
            damaged = quarter_files()[rc_name].replace(b"100", b"999", 1)
            (target / rc_name).write_bytes(damaged)
            preparation.prepare_quarter(QUARTER, txt_dir, cache_dir, client)
            self.assertEqual((target / rc_name).read_bytes(), quarter_files()[rc_name])
            self.assertEqual(len(client.calls), 1)

    def test_revalidates_entire_archive_inventory_not_only_required_schedules(self):
        contents = quarter_files()
        optional_name = "FFIEC CDR Call Schedule RIA 03312024.txt"
        contents[optional_name] = b"IDRSSD\tRIAD3210\n101\t100\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            txt_dir, cache_dir = root / "TXT", root / "cache"
            client = DownloadClient(archive_bytes(contents))
            first = preparation.prepare_quarter(QUARTER, txt_dir, cache_dir, client)
            target = Path(first["directory"])
            (target / optional_name).unlink()
            preparation.prepare_quarter(QUARTER, txt_dir, cache_dir, client)
            self.assertEqual((target / optional_name).read_bytes(), contents[optional_name])
            self.assertEqual(len(client.calls), 1)

    def test_refresh_downloads_new_archive_and_invalid_refresh_keeps_existing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            txt_dir, cache_dir = root / "TXT", root / "cache"
            client = DownloadClient()
            first = preparation.prepare_quarter(QUARTER, txt_dir, cache_dir, client)
            target = Path(first["directory"])
            readme = target / "readme.md"
            readme.write_text("Existing documentation remains in this folder.\n")
            (target / ".DS_Store").write_bytes(b"Finder metadata")
            preparation.prepare_quarter(QUARTER, txt_dir, cache_dir, client)
            self.assertEqual(len(client.calls), 1)
            self.assertFalse((root / "FFIEC_backups").exists())
            contents = quarter_files()
            rc_name = "FFIEC CDR Call Schedule RC 03312024.txt"
            contents[rc_name] = contents[rc_name].replace(b"100", b"123", 1)
            client.payload = archive_bytes(contents)
            preparation.prepare_quarter(QUARTER, txt_dir, cache_dir, client, refresh=True)
            self.assertEqual(len(client.calls), 2)
            self.assertEqual((target / rc_name).read_bytes(), contents[rc_name])
            self.assertEqual(readme.read_text(), "Existing documentation remains in this folder.\n")
            archive_before = (cache_dir / "archives/20240331.zip").read_bytes()
            client.payload = b"<html>Temporary service failure</html>"
            with self.assertRaises(preparation.PreparationError):
                preparation.prepare_quarter(QUARTER, txt_dir, cache_dir, client, refresh=True)
            self.assertEqual((target / rc_name).read_bytes(), contents[rc_name])
            self.assertEqual((cache_dir / "archives/20240331.zip").read_bytes(), archive_before)

    def test_invalid_download_does_not_publish_a_completed_quarter(self):
        for payload in (b"<html>Try again later</html>", archive_bytes()[:-22]):
            with self.subTest(payload_length=len(payload)), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                txt_dir, cache_dir = root / "TXT", root / "cache"
                with self.assertRaises(preparation.PreparationError):
                    preparation.prepare_quarter(QUARTER, txt_dir, cache_dir, DownloadClient(payload))
                self.assertFalse((txt_dir / "FFIEC CDR Call Bulk All Schedules 20240331").exists())
                self.assertFalse((cache_dir / "quarters/20240331.json").exists())

    def test_unmanaged_existing_folder_is_preserved_when_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            txt_dir, cache_dir = root / "TXT", root / "cache"
            target = txt_dir / "FFIEC CDR Call Bulk All Schedules 20240331"
            target.mkdir(parents=True)
            original_marker = b"Existing user data must survive replacement."
            (target / "existing_notes.txt").write_bytes(original_marker)
            preparation.prepare_quarter(QUARTER, txt_dir, cache_dir, DownloadClient())
            for name, contents in quarter_files().items():
                self.assertEqual((target / name).read_bytes(), contents)
            saved = [path for path in root.rglob("existing_notes.txt")
                     if path.parent != target and path.read_bytes() == original_marker]
            self.assertEqual(len(saved), 1)
            self.assertFalse((target / "existing_notes.txt").exists())


if __name__ == "__main__":
    unittest.main()
