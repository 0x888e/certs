import argparse
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

import download


class PrivateFileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    @unittest.skipUnless(os.name == 'posix', 'POSIX file permissions')
    def test_private_before_first_write_with_permissive_umask(self):
        target = self.root / 'calibration_01.bin'
        real_fdopen = os.fdopen
        observed_modes = []

        def observe_open(descriptor, mode):
            observed_modes.append(stat.S_IMODE(os.fstat(descriptor).st_mode))
            self.assertEqual(os.fstat(descriptor).st_size, 0)
            return real_fdopen(descriptor, mode)

        old_umask = os.umask(0o000)
        try:
            with mock.patch.object(download.os, 'fdopen', side_effect=observe_open):
                download.write_private_file(target, b'synthetic credential bytes')
        finally:
            os.umask(old_umask)
        self.assertEqual(observed_modes, [0o600])
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertEqual(target.read_bytes(), b'synthetic credential bytes')

    def test_existing_file_is_not_truncated(self):
        target = self.root / 'mfg.dat'
        target.write_bytes(b'preserve')
        with self.assertRaises(FileExistsError):
            download.write_private_file(target, b'replace')
        self.assertEqual(target.read_bytes(), b'preserve')

    @unittest.skipUnless(os.name == 'posix', 'symlink creation')
    def test_symlink_is_not_followed_or_removed(self):
        original = self.root / 'original'
        original.write_bytes(b'preserve')
        target = self.root / 'calibration_01.bin'
        target.symlink_to(original)
        with self.assertRaises(FileExistsError):
            download.write_private_file(target, b'replace')
        self.assertTrue(target.is_symlink())
        self.assertEqual(original.read_bytes(), b'preserve')

    @unittest.skipUnless(os.name == 'posix', 'symlink creation')
    def test_dangling_symlink_is_not_followed(self):
        original = self.root / 'missing'
        target = self.root / 'calibration_01.bin'
        target.symlink_to(original)
        with self.assertRaises(FileExistsError):
            download.write_private_file(target, b'replace')
        self.assertTrue(target.is_symlink())
        self.assertFalse(original.exists())

    def test_failed_write_removes_only_new_file(self):
        target = self.root / 'calibration_01.bin'
        with self.assertRaises(TypeError):
            download.write_private_file(target, None)
        self.assertFalse(target.exists())


class RootCertificateNameTests(unittest.TestCase):
    def test_expected_names(self):
        for name in ('attroot2031.der', 'attsubca2021.der', 'a-b_c.der', 'a'*124+'.der'):
            with self.subTest(name=name):
                self.assertTrue(download.is_safe_der_basename(name))

    def test_reject_paths_and_non_der_names(self):
        for name in ('/tmp/escape.der', '../escape.der', 'a/escape.der',
                     'a\\escape.der', 'a..der', '.hidden.der', 'a.pem',
                     'a'*125+'.der', '', ' a.der', 'a.der\n', 'é.der'):
            with self.subTest(name=name):
                self.assertFalse(download.is_safe_der_basename(name))


class DownloadOutputTests(unittest.TestCase):
    def run_download(self, root, certificate_list):
        args = argparse.Namespace(host="unused", port=80, out_dir=root,
                                  force_model=download.Model.BGW320, parallelism=1)
        responses = [b"synthetic hosts", certificate_list, b"\x30\x82synthetic DER"]
        with mock.patch.object(download, "get_response_body", side_effect=responses) as request, \
             mock.patch.object(download, "exploitable", return_value=True), \
             mock.patch.object(download, "Pool") as pool, \
             mock.patch("builtins.print"):
            pool.return_value.__enter__.return_value.starmap.return_value = [b"synthetic calibration"]
            try:
                download.download(args)
            except SystemExit as error:
                return request.call_args_list, error.code
            return request.call_args_list, 0

    def test_reject_remote_path_before_request_or_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "output"
            root.mkdir()
            requests, code = self.run_download(root, b"1:1:0:../escape.der")
            self.assertEqual(code, 1)
            self.assertEqual(len(requests), 2)
            self.assertFalse((root.parent / "escape.der").exists())
            self.assertEqual(list(root.iterdir()), [root / "calibration_01.bin"])

    def test_blank_lines_and_valid_root_certificate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            requests, code = self.run_download(root, b"# comment\n\n1:1:0:attroot2031.der\n")
            self.assertEqual(code, 0)
            self.assertEqual(len(requests), 3)
            self.assertEqual((root / "attroot2031.der").read_bytes(), b"\x30\x82synthetic DER")
            if os.name == "posix":
                for path in root.iterdir():
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)


if __name__ == '__main__':
    unittest.main()
