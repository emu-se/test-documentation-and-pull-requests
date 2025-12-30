import unittest
from unittest.mock import MagicMock, patch, call
import sys
import os
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from services.github_service import GithubService
from models import Repository, PullRequest

class TestGithubService(unittest.TestCase):
    def setUp(self):
        self.github_service = GithubService("fake_token")

    @patch('services.github_service.requests.request')
    @patch('time.sleep') 
    def test_safe_request_success(self, mock_sleep, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        resp = self.github_service._safe_request("http://url", "get")
        self.assertEqual(resp, mock_response)
        mock_sleep.assert_not_called()

    @patch('services.github_service.requests.request')
    @patch('time.sleep') 
    def test_safe_request_rate_limit(self, mock_sleep, mock_request):
        resp_403 = MagicMock()
        resp_403.status_code = 403
        resp_403.headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1000"}
        
        resp_200 = MagicMock()
        resp_200.status_code = 200

        mock_request.side_effect = [resp_403, resp_200]
        
        with patch('time.time', return_value=900):
            resp = self.github_service._safe_request("http://url", "get")
        
        self.assertEqual(resp, resp_200)
        self.assertTrue(mock_sleep.called) 

    @patch('services.github_service.requests.request')
    @patch('time.sleep')
    def test_safe_request_server_error(self, mock_sleep, mock_request):
        resp_500 = MagicMock()
        resp_500.status_code = 500
        
        resp_200 = MagicMock()
        resp_200.status_code = 200

        mock_request.side_effect = [resp_500, resp_200]

        resp = self.github_service._safe_request("http://url", "get")
        
        self.assertEqual(resp, resp_200)
        mock_sleep.assert_called_with(10)

    @patch('services.github_service.requests.request')
    def test_safe_request_other_error(self, mock_request):
        resp_404 = MagicMock()
        resp_404.status_code = 404
        mock_request.return_value = resp_404

        with self.assertRaises(Exception):
            self.github_service._safe_request("http://url", "get")

    @patch('services.github_service.GithubService._safe_request')
    def test_get_repository_success(self, mock_safe_request):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'data': {
                'repository': {
                    'nameWithOwner': 'owner/repo',
                    'stargazerCount': 10,
                    'forkCount': 5,
                    'watchers': {'totalCount': 2}
                }
            }
        }
        mock_safe_request.return_value = mock_resp

        repo = self.github_service.get_repository("owner/repo")
        self.assertIsInstance(repo, Repository)
        self.assertEqual(repo.full_name, "owner/repo")

    @patch('services.github_service.GithubService._safe_request')
    @patch('services.github_service.csvService')
    def test_get_repository_error_response(self, mock_csv_service, mock_safe_request):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'errors': ['some error']}
        mock_safe_request.return_value = mock_resp

        repo = self.github_service.get_repository("owner/repo")
        self.assertIsNone(repo)
        mock_csv_service.write_error_log.assert_called()

    @patch('services.github_service.GithubService._safe_request')
    def test_get_pull_requests(self, mock_safe_request):
        repo = MagicMock()
        repo.full_name = "owner/repo"

        pr_data = [{'number': 1}, {'number': 2}]
        
        mock_resp_p1 = MagicMock()
        mock_resp_p1.json.return_value = pr_data
        
        mock_resp_p2 = MagicMock()
        mock_resp_p2.json.return_value = []

        mock_safe_request.side_effect = [mock_resp_p1, mock_resp_p2]

        prs = list(self.github_service.get_pull_requests(repo))
        
        self.assertEqual(len(prs), 2)
        self.assertIsInstance(prs[0], PullRequest)
        self.assertEqual(prs[0].number, 1)

    @patch('services.github_service.GithubService._safe_request')
    def test_get_files(self, mock_safe_request):
        pr = MagicMock()
        pr.number = 1
        pr.base.repo.full_name = "owner/repo"

        file_data = [{'filename': 'file1.py'}, {'filename': 'file2.py'}]
        
        mock_resp_p1 = MagicMock()
        mock_resp_p1.json.return_value = file_data
        
        mock_resp_p2 = MagicMock()
        mock_resp_p2.json.return_value = []

        mock_safe_request.side_effect = [mock_resp_p1, mock_resp_p2]

        files = list(self.github_service.get_files(pr))
        
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0].filename, 'file1.py')

if __name__ == '__main__':
    unittest.main()
