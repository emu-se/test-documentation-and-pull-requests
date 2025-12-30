import unittest
from unittest.mock import MagicMock, patch, call
import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import calculate

class TestCalculate(unittest.TestCase):

    def test_convert_to_datetime_z_format(self):
        dt = calculate.convert_to_datetime("2023-01-01T12:00:00Z")
        self.assertEqual(dt, datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc))

    def test_convert_to_datetime_iso_no_z(self):
        dt = calculate.convert_to_datetime("2023-01-01T12:00:00+00:00")
        self.assertEqual(dt, datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        
    def test_convert_to_datetime_naive(self):
        dt = calculate.convert_to_datetime("2023-01-01T12:00:00")
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_get_repo_full_name_simple(self):
        url = "https://github.com/owner/repo"
        self.assertEqual(calculate.get_repo_full_name(url), "owner/repo")
        
    def test_get_repo_full_name_trailing_slash(self):
        url_slash = "https://github.com/owner/repo/"
        self.assertEqual(calculate.get_repo_full_name(url_slash), "owner/repo")

    def test_get_repo_full_name_query_params(self):
        url_params = "https://github.com/owner/repo?param=1"
        self.assertEqual(calculate.get_repo_full_name(url_params), "owner/repo")

    def test_get_repo_full_name_invalid(self):
        self.assertEqual(calculate.get_repo_full_name("invalid"), "")

    def test_copy_relevant_fields(self):
        repo_info = {
            'GitHub': 'url',
            'Doc_type': 'readme',
            'Irrelevant': 'info',
            'Unit': 'yes'
        }
        copied = calculate.copy_relevant_fields(repo_info)
        self.assertIn('GitHub', copied)
        self.assertIn('Doc_type', copied)
        self.assertIn('Unit', copied)
        self.assertNotIn('Irrelevant', copied)
        self.assertIsNone(copied.get('Coverage'))

    def test_calculate_test_engagement_ratio(self):
        merged_prs = [
            {'touches_test_files': 'True', 'touches_production_files': 'True'},
            {'touches_test_files': 'False', 'touches_production_files': 'True'},
            {'touches_test_files': 'True', 'touches_production_files': 'False'},
            {'touches_test_files': 'False', 'touches_production_files': 'False'},
        ]
        info = {}
        calculate.calculate_test_engagement_ratio(iter(merged_prs), info)
        
        self.assertEqual(info['count_touches_production'], 2)
        self.assertEqual(info['count_touches_tests'], 1)
        self.assertEqual(info['test_engagement_ratio'], 0.5)

    def test_calculate_test_engagement_ratio_divide_by_zero(self):
        merged_prs = []
        info = {}
        calculate.calculate_test_engagement_ratio(iter(merged_prs), info)
        self.assertIsNone(info['test_engagement_ratio'])

    @patch('calculate.githubService')
    @patch('calculate.csvService')
    def test_which_files_touched_both(self, mock_csv_service, mock_github_service):
        mock_pr = MagicMock()
        mock_pr.number = 123
        mock_pr.base.repo.full_name = "owner/repo"

        file_test = MagicMock()
        file_test.is_test_file.return_value = True
        file_test.is_production_file.return_value = False

        file_prod = MagicMock()
        file_prod.is_test_file.return_value = False
        file_prod.is_production_file.return_value = True

        mock_github_service.get_files.return_value = [file_test, file_prod]
        result = calculate.which_files_were_touched(mock_pr)
        self.assertTrue(result['touches_test_files'])
        self.assertTrue(result['touches_production_files'])

    @patch('calculate.githubService')
    @patch('calculate.csvService')
    def test_which_files_touched_production_only(self, mock_csv_service, mock_github_service):
        mock_pr = MagicMock()
        mock_pr.number = 123
        mock_pr.base.repo.full_name = "owner/repo"

        file_prod = MagicMock()
        file_prod.is_test_file.return_value = False
        file_prod.is_production_file.return_value = True

        mock_github_service.get_files.return_value = [file_prod]
        result = calculate.which_files_were_touched(mock_pr)
        self.assertFalse(result['touches_test_files'])
        self.assertTrue(result['touches_production_files'])

    @patch('calculate.githubService')
    @patch('calculate.csvService')
    def test_which_files_touched_api_error(self, mock_csv_service, mock_github_service):
        mock_pr = MagicMock()
        mock_pr.number = 123
        mock_pr.base.repo.full_name = "owner/repo"
        
        mock_github_service.get_files.side_effect = Exception("API error")
        calculate.which_files_were_touched(mock_pr)
        mock_csv_service.write_error_log.assert_called()

    @patch('calculate.githubService')
    @patch('calculate.csvService')
    def test_get_merged_prs(self, mock_csv_service, mock_github_service):
        mock_repo = MagicMock()
        mock_repo.get_sanitized_name.return_value = "repo_clean"
        mock_repo.get_checkpoint_path.return_value = "checkpoint.csv"
        
        mock_csv_service.read_csv.return_value = [{'number': '100'}]
        
        pr_old = MagicMock(number=100)
        
        pr_not_merged = MagicMock(number=101, merge_commit_sha=None)
        
        pr_before_date = MagicMock(number=102, merge_commit_sha='sha', merged_at=None, closed_at="2020-01-01T00:00:00Z")
        
        pr_valid = MagicMock(number=103, merge_commit_sha='sha', merged_at="2025-06-01T00:00:00Z")
        pr_valid.base.repo.full_name = "owner/repo"
        
        mock_github_service.get_pull_requests.return_value = iter([pr_old, pr_not_merged, pr_valid, pr_before_date])
        
        file_prod = MagicMock()
        file_prod.is_test_file.return_value = False
        file_prod.is_production_file.return_value = True
        mock_github_service.get_files.return_value = [file_prod]

        calculate.get_merged_prs(mock_repo)

        mock_csv_service.save_csv_row.assert_any_call("checkpoint.csv", {
            'repo_name': 'repo_clean', 'number': 101, 'touches_test_files': False, 
            'touches_production_files': False, 'notes': 'not merged'
        })
        
        mock_csv_service.save_csv_row.assert_any_call("checkpoint.csv", {
            'repo_name': 'repo_clean', 'number': 103, 'touches_test_files': False, 
            'touches_production_files': True, 'notes': None
        })

if __name__ == '__main__':
    unittest.main()
