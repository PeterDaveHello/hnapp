import io
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout, redirect_stderr

from cron import main, cli, every_1_min


class CronCliTests(unittest.TestCase):

    def test_cron_main_success(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(['test']), 0)

    def test_cron_main_usage_error(self):
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            exit_code = main(['update'])
        self.assertEqual(exit_code, 2)
        combined = out.getvalue() + err.getvalue()
        self.assertIn('Missing argument', combined)

    def test_legacy_command_registered(self):
        self.assertIn('every_1_min', cli.commands)
        self.assertIs(cli.commands['every_1_min'], every_1_min)

    def test_scraper_import_standalone(self):
        project_root = os.path.dirname(os.path.dirname(__file__))
        result = subprocess.run(
            [sys.executable, '-c', 'from scraper import Scraper; print(Scraper.__name__)'],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)

    def test_update_rejects_non_positive_ids(self):
        args_list = [
            ['update', '--', '0', '10', '0'],
            ['update', '--', '-1', '10', '0'],
            ['update', '--', '1', '0', '0'],
            ['update', '--', '1', '-10', '0'],
        ]
        for args in args_list:
            with self.subTest(args=args):
                out = io.StringIO()
                err = io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    exit_code = main(args)
                self.assertEqual(exit_code, 2)
                combined = out.getvalue() + err.getvalue()
                self.assertIn('positive integers', combined)


if __name__ == '__main__':
    unittest.main()
