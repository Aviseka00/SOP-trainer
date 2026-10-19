import copy
import unittest
from unittest.mock import patch
from sop_studio.summary import build_brief, brief_scenes, brief_current, polish_brief

SOURCE = '''Title: Test cleaning
SOP number: CL-01
1. Inspect the equipment before starting work.
2. Apply approved soap to both hands.
3. Rub hands for 20 seconds before rinsing.
4. Never bypass the equipment safety interlock.
5. Record the cleaning in the logbook.
6. Store materials in the designated container.
7. Check the room before leaving work.'''


class SummaryTests(unittest.TestCase):
    def test_safety_and_numeric_criteria_survive_short_target(self):
        brief = build_brief(SOURCE, 3)
        narration = ' '.join(x['speech'] for x in brief['points'])
        self.assertIn('20 seconds', narration)
        self.assertIn('Never bypass', narration)
        for point in brief['points']:
            self.assertEqual(point['speech'], SOURCE.splitlines()[point['source_line']-1])
        self.assertNotIn('Title:', narration)
        self.assertGreater(brief['omitted_segments'], 0)

    def test_scene_provenance_and_changed_source_guard(self):
        brief = build_brief(SOURCE)
        scenes = brief_scenes(brief, SOURCE)
        self.assertEqual(len(brief['points']), len(scenes))
        self.assertTrue(all(not s['approved'] and s['layout'] == 'Presenter side-by-side' for s in scenes))
        self.assertEqual(brief['points'][0]['original_instruction'], scenes[0]['original_instruction'])
        self.assertFalse(brief_current(brief, SOURCE+' changed'))
        with self.assertRaisesRegex(ValueError, 'Source changed'):
            brief_scenes(brief, SOURCE+' changed')

    def test_model_cannot_drop_critical_points(self):
        brief = build_brief(SOURCE)
        before = copy.deepcopy(brief)
        with patch('sop_studio.llm.models', return_value=['test']), patch('sop_studio.llm.request', return_value={'response':'{"points": []}'}):
            with self.assertRaisesRegex(ValueError, 'omitted points'):
                polish_brief(brief, 'test')
        self.assertEqual(before, brief)
