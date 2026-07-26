from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from connection_model import (  # noqa: E402
    ConnectionConfig,
    ConnectionConfigError,
)


class ConnectionModelTests(unittest.TestCase):
    def test_repository_config_is_valid(self):
        path = Path(__file__).parents[1] / 'config' / 'connections.json'
        config = ConnectionConfig.from_path(path)
        self.assertEqual(len(config.connections), 3)
        self.assertEqual(
            config.connection('contestantSnapshots')['port'],
            7000,
        )

    def test_rejects_invalid_ports_and_protocols(self):
        data = {
            'version': 1,
            'connections': [{
                'id': 'input',
                'label': 'Input',
                'direction': 'receive',
                'protocol': 'tcp',
                'enabled': True,
                'localAddress': '',
                'port': 0,
                'purpose': 'contestantSnapshot',
            }],
        }
        with self.assertRaisesRegex(
            ConnectionConfigError,
            'currently supports only udp',
        ):
            ConnectionConfig(data)

    def test_duplicate_enabled_receive_bindings_are_rejected(self):
        connection = {
            'id': 'a',
            'label': 'A',
            'direction': 'receive',
            'protocol': 'udp',
            'enabled': True,
            'localAddress': '',
            'port': 7000,
            'purpose': 'contestantSnapshot',
        }
        duplicate = dict(connection, id='b', label='B')
        with self.assertRaisesRegex(ConnectionConfigError, 'cannot share'):
            ConnectionConfig({
                'version': 1,
                'connections': [connection, duplicate],
            })

    def test_direction_specific_fields_are_strict(self):
        with self.assertRaisesRegex(ConnectionConfigError, 'unknown field'):
            ConnectionConfig({
                'version': 1,
                'connections': [{
                    'id': 'output',
                    'label': 'Output',
                    'direction': 'send',
                    'protocol': 'udp',
                    'enabled': True,
                    'address': '127.0.0.1',
                    'localAddress': '',
                    'port': 7001,
                    'purpose': 'logicState',
                }],
            })


if __name__ == '__main__':
    unittest.main()
