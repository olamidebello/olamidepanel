import json,re,unittest
from pathlib import Path
class ModuleAuditTest(unittest.TestCase):
 def test_every_catalog_tool_audited_once(self):
  root=Path(__file__).parents[1]
  source=(root/'panel/static/app.js').read_text()
  groups=re.search(r'const groups=(\{.*?\});',source).group(1)
  catalog=json.loads(re.sub(r'([,{])(\w+):',r'\1"\2":',groups).replace("'",'"'))
  rows=json.loads((root/'panel/module-audit.json').read_text())
  expected={(category,name) for category,names in catalog.items() for name in names}
  self.assertEqual(expected,{(r['category'],r['name']) for r in rows})
  self.assertEqual(len(expected),len(rows))
  available=set(re.findall(r"'([^']+)'",re.search(r'const implemented=\[(.*?)\];',source).group(1)))
  self.assertEqual(available,{r['name'] for r in rows if r['status']!='not implemented'})
