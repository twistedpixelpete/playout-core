from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from take_readiness import assess_decoder_readiness  # noqa: E402


def assess(**changes):
    values = {
        'opened': False,
        'opening': True,
        'open_failed': False,
        'decode_errors': False,
        'fully_pre_read': False,
        'num_pre_read_frames': 0,
        'requested_pre_read_frames': 12,
        'movie_length_frames': 100,
        'minimum_start_frames': 1,
        'elapsed_seconds': 0.5,
        'timeout_seconds': 10.0,
    }
    values.update(changes)
    return assess_decoder_readiness(**values)


class TakeReadinessTests(unittest.TestCase):
    def test_ready_when_full_pre_read_is_reported(self):
        self.assertEqual(
            assess(opened=True, fully_pre_read=True).state,
            'READY',
        )

    def test_ready_when_minimum_start_frame_is_available(self):
        self.assertEqual(
            assess(opened=True, num_pre_read_frames=1).state,
            'READY',
        )

    def test_minimum_can_be_increased_for_high_bitrate_media(self):
        decision = assess(
            opened=True,
            minimum_start_frames=3,
            num_pre_read_frames=3,
        )
        self.assertEqual(decision.state, 'READY')
        self.assertEqual(decision.required_frames, 3)

    def test_open_movie_waits_until_a_decoded_frame_exists(self):
        self.assertEqual(
            assess(opened=True, num_pre_read_frames=0).state,
            'WAITING',
        )

    def test_open_failure_is_immediate_error(self):
        self.assertEqual(assess(open_failed=True).state, 'ERROR')

    def test_decode_error_is_immediate_error(self):
        self.assertEqual(assess(decode_errors=True).state, 'ERROR')

    def test_stalled_decoder_times_out_with_diagnostics(self):
        decision = assess(elapsed_seconds=10.0)
        self.assertEqual(decision.state, 'ERROR')
        self.assertIn('timed out', decision.reason)
        self.assertIn('pre-read=0/1', decision.reason)


if __name__ == '__main__':
    unittest.main()
