import unittest
from unittest.mock import mock_open, patch, MagicMock
import sys
import os
import csv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from services.csv_service import CsvService

class TestCsvService(unittest.TestCase):
    def setUp(self):
        self.csv_service = CsvService()

    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    @patch('services.csv_service.datetime')
    def test_write_error_log(self, mock_datetime, mock_file, mock_makedirs):
        mock_datetime.now.return_value.isoformat.return_value = "2023-01-01T00:00:00"
        
        self.csv_service.write_error_log("Test error")
        
        mock_makedirs.assert_called_with("logs", exist_ok=True)
        
        mock_file.assert_called_with("logs/error_log.txt", "a")
        
        mock_file().write.assert_called_with("2023-01-01T00:00:00 - Test error\n")

    @patch('os.path.exists')
    def test_read_csv_not_exists(self, mock_exists):
        mock_exists.return_value = False
        result = list(self.csv_service.read_csv("nonexistent.csv"))
        self.assertEqual(result, [])

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open, read_data="col1,col2\nval1,val2")
    def test_read_csv_success(self, mock_file, mock_exists):
        mock_exists.return_value = True
        
        rows = list(self.csv_service.read_csv("test.csv"))
        
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['col1'], 'val1')
        self.assertEqual(rows[0]['col2'], 'val2')

    @patch('os.makedirs')
    @patch('os.path.isfile')
    @patch('os.path.getsize')
    @patch('builtins.open', new_callable=mock_open)
    def test_save_csv_row_new_file(self, mock_file, mock_getsize, mock_isfile, mock_makedirs):
        mock_isfile.return_value = False
        mock_getsize.return_value = 0
        
        data = {'col1': 'val1', 'col2': 'val2'}
        self.csv_service.save_csv_row("new.csv", data)
        
        mock_makedirs.assert_called_with(".", exist_ok=True)
        mock_file.assert_called_with("new.csv", 'a', newline='')
        
        self.assertTrue(mock_file().write.called)
        
        writes = [args[0] for args, _ in mock_file().write.call_args_list]
        self.assertTrue(any('col1,col2' in w for w in writes))
        self.assertTrue(any('val1,val2' in w for w in writes))

    @patch('os.makedirs')
    @patch('os.path.isfile')
    @patch('os.path.getsize')
    @patch('builtins.open', new_callable=mock_open)
    def test_save_csv_row_append(self, mock_file, mock_getsize, mock_isfile, mock_makedirs):
        mock_isfile.return_value = True
        mock_getsize.return_value = 100 
        
        data = {'col1': 'val1', 'col2': 'val2'}
        self.csv_service.save_csv_row("existing.csv", data)
        
        writes = [args[0] for args, _ in mock_file().write.call_args_list]
        self.assertFalse(any('col1,col2' in w for w in writes))
        self.assertTrue(any('val1,val2' in w for w in writes))

if __name__ == '__main__':
    unittest.main()
