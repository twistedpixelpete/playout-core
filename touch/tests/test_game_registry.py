import json
from pathlib import Path
import sys
import unittest


TOUCH = Path(__file__).parents[1]
SCRIPTS = TOUCH / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from game_registry import RegistryError, VariantRegistry  # noqa: E402


class GameRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = VariantRegistry.from_path(
            TOUCH / 'config' / 'game_archetypes.json'
        )

    def test_loads_all_configured_variants(self):
        variants = self.registry.list_variants()
        self.assertEqual(len(variants), 8)
        self.assertEqual(variants[0]['id'], 'contestantEliminationGrid')

    def test_creates_independent_project_from_variant(self):
        first = self.registry.create(
            'show_a',
            'territoryTimedDuel',
            {'board': {'width': 10, 'height': 10}},
        )
        second = self.registry.create(
            'show_b',
            'territoryTimedDuel',
            {'board': {'width': 8, 'height': 8}},
        )
        first.configure({'duelSeconds': 45})
        self.assertEqual(first.snapshot()['revision'], 1)
        self.assertEqual(second.snapshot()['revision'], 0)
        self.assertEqual(second.snapshot()['settings']['board']['width'], 8)

    def test_rejects_unknown_variant(self):
        with self.assertRaisesRegex(RegistryError, 'Unknown variant'):
            self.registry.create('show', 'missing')

    def test_rejects_non_json_project_settings(self):
        with self.assertRaisesRegex(RegistryError, 'strict JSON'):
            self.registry.create(
                'show',
                'hiddenValueOffer',
                {'bad': float('nan')},
            )

    def test_snapshots_round_trip_as_json(self):
        project = self.registry.create(
            'quiz',
            'wagerableClueBoard',
            {'contestants': 3},
        )
        self.assertEqual(
            json.loads(json.dumps(project.snapshot())),
            project.snapshot(),
        )


if __name__ == '__main__':
    unittest.main()
