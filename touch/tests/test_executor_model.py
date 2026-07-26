from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from executor_model import ExecutorConfig, ExecutorConfigError  # noqa: E402


def config(actions=None):
    return {
        'version': 1,
        'buttons': [{
            'id': '001',
            'label': 'GO',
            'color': 'green',
            'actions': actions or [
                {'type': 'playback.take', 'clipId': '1001'}
            ],
        }],
    }


class ExecutorModelTests(unittest.TestCase):
    def test_multiple_actions_are_ordered_in_one_batch(self):
        model = ExecutorConfig(config([
            {'type': 'logic.resetEpisode'},
            {'type': 'playback.take', 'clipId': '1001'},
        ]))
        plan = model.plan('001')
        self.assertEqual(len(plan), 1)
        self.assertEqual(
            [action['type'] for action in plan[0].actions],
            ['logic.resetEpisode', 'playback.take'],
        )

    def test_wait_splits_actions_into_delayed_batches(self):
        model = ExecutorConfig(config([
            {'type': 'playback.take', 'clipId': '1001'},
            {'type': 'wait', 'durationMs': 750},
            {'type': 'playback.take', 'clipId': '1002'},
        ]))
        plan = model.plan('001')
        self.assertEqual([batch.at_ms for batch in plan], [0, 750])
        self.assertEqual(plan[1].actions[0]['clipId'], '1002')

    def test_unknown_actions_and_options_are_rejected(self):
        with self.assertRaisesRegex(ExecutorConfigError, 'unknown action type'):
            ExecutorConfig(config([{'type': 'system.shell'}]))
        with self.assertRaisesRegex(ExecutorConfigError, 'unknown field'):
            ExecutorConfig(config([{
                'type': 'playback.take',
                'clipId': '1001',
                'python': 'unsafe',
            }]))

    def test_duplicate_button_ids_are_rejected(self):
        data = config()
        data['buttons'].append(dict(data['buttons'][0]))
        with self.assertRaisesRegex(ExecutorConfigError, 'Duplicate'):
            ExecutorConfig(data)

    def test_yellow_is_reserved_for_status_not_buttons(self):
        data = config()
        data['buttons'][0]['color'] = 'yellow'
        with self.assertRaisesRegex(ExecutorConfigError, 'color must be'):
            ExecutorConfig(data)

    def test_wait_only_button_is_rejected(self):
        with self.assertRaisesRegex(
            ExecutorConfigError,
            'executable action',
        ):
            ExecutorConfig(config([
                {'type': 'wait', 'durationMs': 100},
            ]))

    def test_connection_send_action_is_supported(self):
        model = ExecutorConfig(config([{
            'type': 'connection.send',
            'connectionId': 'logicStateOutput',
            'payload': {'message': 'hello'},
        }]))
        action = model.plan('001')[0].actions[0]
        self.assertEqual(action['connectionId'], 'logicStateOutput')

    def test_explicit_cancel_pending_action_is_supported(self):
        model = ExecutorConfig(config([
            {'type': 'executor.cancelPending'},
            {'type': 'playback.take', 'clipId': '1001'},
        ]))
        actions = model.plan('001')[0].actions
        self.assertEqual(actions[0]['type'], 'executor.cancelPending')

    def test_repository_executor_config_is_valid(self):
        path = Path(__file__).parents[1] / 'config' / 'executors.json'
        model = ExecutorConfig.from_path(path)
        self.assertGreaterEqual(len(model.buttons), 1)
        self.assertEqual(len(model.buttons), 16)
        self.assertTrue(model.plan('001'))


if __name__ == '__main__':
    unittest.main()
