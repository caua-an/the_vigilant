import unittest
from unittest.mock import patch

from vigilant.linux import minimize_blocked_app


class LinuxMonitoringTest(unittest.TestCase):
    @patch('vigilant.linux.subprocess.run')
    @patch('vigilant.linux.subprocess.check_output', side_effect=['42', '0', 'WM_CLASS = "app", "FocusApp"'])
    @patch('vigilant.linux.shutil.which', return_value='/usr/bin/tool')
    def test_minimizes_only_matching_active_window(self, which, output, run):
        self.assertTrue(minimize_blocked_app([{'id': 'focusapp'}]))
        self.assertEqual(run.call_args.args[0], ['xdotool', 'windowminimize', '42'])
        output.side_effect = ['42', '0', 'WM_CLASS = "app", "Other"']
        run.reset_mock()
        self.assertFalse(minimize_blocked_app([{'id': 'focusapp'}]))
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
