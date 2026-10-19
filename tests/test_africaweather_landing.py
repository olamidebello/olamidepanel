import importlib.util,json,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
ROOT=Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('hub',ROOT/'deploy/africaweather/server.py')
hub=importlib.util.module_from_spec(spec);spec.loader.exec_module(hub)
class ForecastTests(unittest.TestCase):
 def payload(self):
  return dict(current=dict(temperature_2m=28,weather_code=0),daily=dict(time=['2026-10-19'],weather_code=[0],temperature_2m_max=[30],temperature_2m_min=[20],precipitation_probability_max=[5]),timezone='Africa/Lagos')
 def response(self,payload):
  res=MagicMock();res.__enter__.return_value=res;res.read.return_value=json.dumps(payload).encode();return res
 def test_all_destinations_unique(self):
  countries=list(hub.COUNTRIES.values())
  self.assertEqual(len(countries),55)
  self.assertEqual(len({c['domain'] for c in countries}),55)
  for c in countries:self.assertEqual(c['domain'],'weather'+c['slug']+'.africandroid.world')
 def test_daily_forecast_preserved(self):
  with patch.object(hub,'urlopen',return_value=self.response(self.payload())) as request:
   data=hub.forecast(hub.COUNTRIES['nigeria'])
   self.assertEqual(data['daily']['temperature_2m_max'],[30])
   self.assertEqual(request.call_count,1)
 def test_unavailable_country_uses_provider(self):
  with patch.object(hub,'urlopen',side_effect=[OSError(),self.response(self.payload())]) as request:
   self.assertIn('daily',hub.forecast(hub.COUNTRIES['nigeria']))
   self.assertTrue(request.call_args.args[0].startswith('https://api.open-meteo.com/v1/forecast?'))
 def test_incomplete_forecast_retries_then_fails(self):
  with patch.object(hub,'urlopen',return_value=self.response({'current':{'temperature_2m':30}})) as request:
   with self.assertRaises(ValueError):hub.forecast(hub.COUNTRIES['nigeria'])
   self.assertEqual(request.call_count,2)
if __name__=='__main__':unittest.main()
