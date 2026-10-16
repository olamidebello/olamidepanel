import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'panel'))
import websites
class WebsitesTest(unittest.TestCase):
    def test_escapes_content(self):
        result=websites.page('<script>alert(1)</script>','A & B')
        self.assertNotIn('<script>',result)
        self.assertIn('&lt;script&gt;',result)
        self.assertIn('A &amp; B',result)
    def test_readonly_cannot_publish(self):
        self.assertEqual(websites.handle('POST','/api/websites',{'role':'readonly'}, {})[0],403)
    def test_title_bounds(self):
        for title in ['', 'a'*101]:
            with self.assertRaises(ValueError):websites.handle('POST','/api/websites',{'role':'user'},{'title':title})
