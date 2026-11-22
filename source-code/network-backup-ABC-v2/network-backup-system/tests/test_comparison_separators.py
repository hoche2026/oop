"""Regression for the extra standalone ! observed on R2 after OSPF restore."""
import unittest

from app.comparison import comparison_lines
import test_complete_release as fixtures
from verify_ospf_restore import recheck


class SeparatorTests(unittest.TestCase):
    CONFIG = 'version 15.2\n!\nhostname R2\n!\ninterface FastEthernet1/0\nend\n'

    def test_extra_separator_at_start_is_not_config_change(self):
        actual = '!\n' + self.CONFIG
        self.assertEqual(comparison_lines(self.CONFIG),
                         comparison_lines(actual))

    def test_extra_separator_in_body_is_not_config_change(self):
        actual = self.CONFIG.replace('interface', '!\ninterface')
        self.assertEqual(comparison_lines(self.CONFIG),
                         comparison_lines(actual))

    def test_real_command_and_nonempty_comment_still_differ(self):
        self.assertNotEqual(comparison_lines(self.CONFIG), comparison_lines(
            self.CONFIG.replace('interface FastEthernet1/0', 'interface FastEthernet1/0\n shutdown')))
        self.assertNotEqual(comparison_lines(self.CONFIG), comparison_lines(
            self.CONFIG.replace('!\nhostname', '! useful comment\nhostname')))

    def test_banner_exclamation_and_header_like_text_are_preserved(self):
        banner = 'banner motd ^C\n!\n! Last configuration change at welcome\n^C\n'
        original = self.CONFIG.replace('end\n', banner + 'end\n')
        actual = original.replace('motd ^C\n!\n', 'motd ^C\n')
        self.assertNotEqual(comparison_lines(original),
                            comparison_lines(actual))
        self.assertIn('!\n', comparison_lines(original))
        self.assertIn('! Last configuration change at welcome\n',
                      comparison_lines(original))

    def test_non_ios_text_not_stripped(self):
        self.assertNotEqual(comparison_lines('hostname R2\n'),
                            comparison_lines('!\nhostname R2\n'))
        self.assertNotEqual(comparison_lines('/system identity set name=MT1\n'),
                            comparison_lines('!\n/system identity set name=MT1\n'))


class RecheckTests(unittest.TestCase):
    def test_successful_recheck_uses_no_mutation(self):
        fixture = fixtures.ReleaseIntegrationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.lab.run('apply')
        fixture.lab._restore(fixture.lab._state())
        fixture.registry['events'].clear()
        results = recheck(fixture.lab)
        self.assertTrue(all(result.status == 'success' for result in results))
        self.assertTrue(
            all(event[0] == 'verify' for event in fixture.registry['events']))
        self.assertTrue(fixture.lab.state_path.exists())


if __name__ == '__main__':
    unittest.main()
