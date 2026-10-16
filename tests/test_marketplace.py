import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'panel'))
import marketplace
class MarketplaceTest(unittest.TestCase):
    def plan(self):return {'name':'Business','description':'Example','price_cents':1500,'disk_gb':30,'bandwidth_gb':500,'websites':5,'enabled':False,'featured':True}
    def test_plan_validation(self):
        self.assertEqual(marketplace.validate_plan(self.plan())['price_cents'],1500)
    def test_reject_invalid_prices(self):
        for value in [-1,1.5,'1500',True]:
            with self.assertRaises(ValueError):marketplace.validate_plan({**self.plan(),'price_cents':value})
    def test_readonly_cannot_submit(self):
        status,_=marketplace.handle('POST','/api/marketplace/orders/create',{'role':'readonly'},{})
        self.assertEqual(status,403)
    def test_user_cannot_manage_plans(self):
        status,_=marketplace.handle('POST','/api/marketplace/plans/save',{'role':'user'},{})
        self.assertEqual(status,403)
    def test_only_pending_can_change(self):
        for state in ['approved','rejected','cancelled']:
            with self.assertRaises(ValueError):marketplace.transition(state,'cancel',True)
    def test_transitions(self):
        self.assertEqual(marketplace.transition('pending','approve',True),'approved')
        self.assertEqual(marketplace.transition('pending','cancel',False),'cancelled')
        with self.assertRaises(ValueError):marketplace.transition('pending','approve',False)
