"""Version 1.8: squad register, week memory and the browser archive allowlist."""
import datetime as dt
import json
import re
import unittest
from pathlib import Path

from studio_state import (DEFAULTS, SQUAD_ID, WEEK_ID, defaults, matches_from_week, matches_to_week,
                          sanitize_squad, sanitize_week, validate_library)

ROOT = Path(__file__).resolve().parents[1]


class ArchiveTests(unittest.TestCase):
    def test_browser_archive_accepts_every_editor(self):
        page = (ROOT/'library_frontend'/'index.html').read_text()
        allowed = set(re.findall(r"'([^']+)'", re.search(r'const TEMPLATES=\[(.*?)\]', page).group(1)))
        self.assertTrue(set(DEFAULTS) <= allowed, set(DEFAULTS)-allowed)
        self.assertTrue({'Rosa', 'Settimana'} <= allowed)
        self.assertEqual(page.count('TEMPLATES.includes'), 2)

    def test_projects_of_new_editors_survive_validation(self):
        projects = {t: {'name': t, 'template': t, 'config': defaults(t)} for t in DEFAULTS}
        library, messages = validate_library(json.loads(json.dumps(dict(schema=1, assets={}, projects=projects))))
        self.assertFalse(messages)
        self.assertEqual(set(library['projects']), set(DEFAULTS))


class SquadTests(unittest.TestCase):
    def test_clean_dedupe_and_limits(self):
        squad = sanitize_squad({'players': [
            {'number': 10, 'name': ' rossi  mario ', 'role': 'C'}, {'number': 999, 'name': 'Bianchi', 'role': 'X'},
            {'number': 3, 'name': 'ROSSI MARIO'}, {'name': ''}, 'junk'] + [{'number': i, 'name': f'P{i}'} for i in range(40)]})
        self.assertEqual(squad[0], {'number': 10, 'name': 'ROSSI MARIO', 'role': 'C'})
        self.assertEqual(squad[1], {'number': 99, 'name': 'BIANCHI', 'role': '-'})
        self.assertEqual(len(squad), 30)
        self.assertEqual(len({p['name'] for p in squad}), 30)

    def test_squad_and_week_leave_the_project_list(self):
        week = dict(match={'opponent': 'UNITED FLERO', 'our_side': 'Ospiti', 'round': 6},
                    standings=[{'pos': 1, 'team': 'UMC', 'pt': 10, 'g': 4}],
                    fixtures=[{'date': '30/10', 'opponent': 'UNITED FLERO', 'side': 'T', 'time': '21:15'}],
                    matches=matches_to_week([dict(home='UNITED FLERO', away='FLAMINGOS', date=dt.date(2026, 10, 30),
                                                  time='21:15', score=None, venue='ORATORIO FLERO', round=6)]))
        raw = dict(schema=1, assets={}, projects={
            SQUAD_ID: {'name': 'Rosa', 'template': 'Rosa', 'config': {'players': [{'number': 1, 'name': 'Bianchi', 'role': 'P'}]}},
            WEEK_ID: {'name': 'Settimana', 'template': 'Settimana', 'config': week}})
        library, messages = validate_library(json.loads(json.dumps(raw)))
        self.assertFalse(messages)
        self.assertEqual(library['projects'], {})
        self.assertEqual(library['squad'][0]['name'], 'BIANCHI')
        self.assertEqual(library['week']['match']['opponent'], 'UNITED FLERO')
        restored = matches_from_week(library['week'])
        self.assertEqual(restored[0]['date'], dt.date(2026, 10, 30))
        self.assertIsNone(restored[0]['score'])

    def test_week_rejects_bad_values(self):
        week = sanitize_week({'match': 'x', 'standings': [{'team': 'A', 'pt': 'lots'}, {'team': ''}],
                              'matches': [{'date': 'ieri'}, {'date': '2026-11-02', 'score': [1, 2]}], 'fixtures': 5})
        self.assertEqual(week['standings'], [{'pos': 1, 'team': 'A', 'pt': 0, 'g': 0, 'v': 0, 'n': 0, 'p': 0, 'gf': 0, 'gs': 0}])
        self.assertEqual(len(week['matches']), 1)
        self.assertEqual(week['fixtures'], [])
        self.assertIsNone(sanitize_week('nope'))


if __name__ == '__main__':
    unittest.main()
