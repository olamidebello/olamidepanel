import importlib.util
from pathlib import Path
import socket
import unittest

spec = importlib.util.spec_from_file_location('weather_dns_preflight', Path(__file__).resolve().parents[1] / 'deploy/weather/dns_preflight.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class DNSPreflight(unittest.TestCase):
    def test_missing_wrong_and_ready_domains(self):
        countries=[{'domain':'weatherghana.africandroid.world'}, {'domain':'weatherkenya.africandroid.world'}, {'domain':'weathertogo.africandroid.world'}]
        def resolve(name, port, **kwargs):
            if 'togo' in name:
                raise socket.gaierror(-2,'Name or service not known')
            address='181.214.149.146' if 'ghana' in name else '192.0.2.1'
            return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(address,port))]
        rows, zone=module.audit(countries,'181.214.149.146',resolve)
        self.assertEqual([r['ready'] for r in rows],[True,False,False])
        self.assertEqual(zone.count('300 IN A 181.214.149.146'),3)
        self.assertIn('weathertogo.africandroid.world. 300 IN A',zone)

    def test_reject_invalid_input(self):
        with self.assertRaises(ValueError):
            module.audit([{'domain':'invalid\nIN NS bad.example'}],'181.214.149.146')
        with self.assertRaises(ValueError):
            module.audit([],'invalid')
