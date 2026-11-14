import importlib.util
import subprocess
import sys
import unittest


class BrandingTests(unittest.TestCase):
    def test_package_and_cli_use_project_name(self):
        self.assertIsNotNone(importlib.util.find_spec('sbswe'))
        result = subprocess.run([sys.executable, '-m', 'sbswe', '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('sbswe', result.stdout)


if __name__ == '__main__':
    unittest.main()
