import importlib.util,sys,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).parents[1]/'panel'))
import database
class AdapterTest(unittest.TestCase):
    def test_parameter_binding_and_commit(self):
        raw=MagicMock()
        with patch.object(database,'configuration',return_value={}),patch.object(database.pymysql,'connect',return_value=raw):
            with database.connect() as con:con.execute('SELECT * FROM users WHERE id=?',(7,))
        raw.cursor.return_value.execute.assert_called_with('SELECT * FROM users WHERE id=%s',(7,))
        raw.commit.assert_called_once();raw.close.assert_called_once()
    def test_rollback_and_close(self):
        raw=MagicMock()
        with patch.object(database,'configuration',return_value={}),patch.object(database.pymysql,'connect',return_value=raw):
            with self.assertRaises(ValueError):
                with database.connect():raise ValueError('failure')
        raw.rollback.assert_called_once();raw.close.assert_called_once()
