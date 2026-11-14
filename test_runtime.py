import tempfile
import unittest
from pathlib import Path

from mswe.env import Environment


class RuntimeTests(unittest.TestCase):
    def test_relative_file_tools_follow_shell_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'child').mkdir()
            env = Environment(cwd=directory, spool_dir=str(root / 'spool'))
            env.execute({'tool': 'bash', 'command': 'cd child'})
            result = env.execute({'tool': 'write_file', 'path': 'example.txt', 'content': 'correct directory'})
            self.assertEqual(result['returncode'], 0)
            self.assertTrue((root / 'child/example.txt').exists())
            self.assertIn('correct directory', env.execute({'tool': 'read_file', 'path': 'example.txt'})['output'])
            self.assertIn('example.txt', env.execute({'tool': 'list_dir'})['output'])

    def test_noninteractive_agent_requires_explicit_yolo(self):
        from mswe.agent import Agent
        from unittest.mock import patch, Mock
        with patch('sys.stdin.isatty', return_value=False):
            with self.assertRaisesRegex(ValueError, '--yolo'):
                Agent(Mock(), Mock(), system_template='test', instance_template='test')
            agent = Agent(Mock(), Mock(), system_template='test', instance_template='test', yolo=True)
            self.assertTrue(agent.config.yolo)

    def test_shell_failure_keeps_exit_code_with_cwd_tracking(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Environment(cwd=directory, spool_dir=str(Path(directory) / 'spool'))
            result = env.execute({'tool': 'bash', 'command': 'exit 7'})
            self.assertEqual(result['returncode'], 7)
            result = env.execute({'tool': 'bash', 'command': 'false'})
            self.assertNotEqual(result['returncode'], 0)


if __name__ == '__main__':
    unittest.main()
