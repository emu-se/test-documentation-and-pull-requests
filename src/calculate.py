import datetime
import os
import re
from typing import Any, Dict, Iterator

from dotenv import load_dotenv
from datetime import datetime, timezone
from models import Repository, PullRequest, File
from services import GithubService, CsvService

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_AUTH_TOKEN")
githubService = GithubService(GITHUB_TOKEN)
csvService = CsvService()

def convert_to_datetime(date: str) -> datetime:
    if date.endswith('Z'):
        parsed = datetime.fromisoformat(date.replace('Z', '+00:00'))
    else:
        parsed = datetime.fromisoformat(date)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed

def calculate_test_engagement_ratio(merged_prs: Iterator[PullRequest], info: Dict[str, Any]):
    count_touches_tests = 0
    count_touches_production = 0

    for pr in merged_prs:
        if pr.get('touches_test_files') == 'True' and pr.get('touches_production_files') == 'True':
            count_touches_tests += 1
        if pr.get('touches_production_files') == 'True':
            count_touches_production += 1

    ter = (count_touches_tests / count_touches_production) if count_touches_production > 0 else None

    info['test_engagement_ratio'] = ter
    info['count_touches_tests'] = count_touches_tests
    info['count_touches_production'] = count_touches_production

def which_files_were_touched(pr: PullRequest) -> Dict[str, bool]:
    touches_test_files = False
    touches_production_files = False

    try:
        files: list[File] = githubService.get_files(pr)

        for f in files:
            if f.is_test_file():
                touches_test_files = True
            elif f.is_production_file():
                touches_production_files = True

            if touches_test_files and touches_production_files:
                break
    except Exception as e:
        csvService.write_error_log(f"Error processing PR #{pr.number} in repo {pr.base.repo.full_name}: {str(e)}")

    return {'touches_test_files': touches_test_files, 'touches_production_files': touches_production_files}

def get_merged_prs(repo: Repository, 
                   start_date: datetime = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc), 
                   end_date: datetime = datetime(2025, 12, 1, 0, 0, tzinfo=timezone.utc)):

    try:
        prs: Iterator[PullRequest] = githubService.get_pull_requests(repo, state='closed')

        checkpoint_path = repo.get_checkpoint_path()
        existing_prs = csvService.read_csv(checkpoint_path)
        existing_pr_numbers = {int(row['number']) for row in existing_prs if 'number' in row}
    except Exception as e:
        csvService.write_error_log(f"Error fetching PRs for repo {repo.full_name}: {str(e)}")
        return

    for pr in prs:
        try:
            # Already been processed
            if pr.number in existing_pr_numbers:
                continue
            # Not merged
            elif pr.merge_commit_sha is None:
                data = {
                        'repo_name': repo.get_sanitized_name(),
                        'number': pr.number,
                        'touches_test_files': False,
                        'touches_production_files': False,
                        'notes': 'not merged'
                        }
                csvService.save_csv_row(checkpoint_path, data)
                continue

            if pr.merged_at is None:
                merged_at = convert_to_datetime(pr.closed_at)
            else:
                merged_at = convert_to_datetime(pr.merged_at)
            
            # Before start date
            if merged_at < start_date:
                break
            # Within date range
            elif start_date <= merged_at <= end_date:
                results = which_files_were_touched(pr)
                data = {
                        'repo_name': repo.get_sanitized_name(),
                        'number': pr.number,
                        'touches_test_files': results['touches_test_files'],
                        'touches_production_files': results['touches_production_files'],
                        'notes': None
                        }
                csvService.save_csv_row(checkpoint_path, data)
        except Exception as e:
            csvService.write_error_log(f"Error processing PR #{pr.number} in repo {repo.full_name}: {str(e)}")
    
def get_repo_full_name(url: str) -> str:
    match = re.search(r'github\.com/([^/?]+/[^/?]+)', url)
    if match:
        return match.group(1)
    return ""

def copy_relevant_fields(repo_info: Dict[str, Any]) -> Dict[str, Any]:
    fields_to_copy = [
        'GitHub', 'Doc_type', 'Language', 'Has_doc', 
        'Has_test_doc', 'How_to_run_tests', 'How_to_write_tests', 'Unit', 
        'Integration', 'e2e', 'Coverage', 'Mocks', 'Best practices/Tips'
    ]
    return {field: repo_info.get(field) for field in fields_to_copy}

if __name__ == "__main__":
    repos = csvService.read_csv('dataset_test_documentation.csv')
    already_processed = csvService.read_csv('output.csv')
    processed_repo_names = {row['GitHub'] for row in already_processed if 'GitHub' in row}
    
    for repo_info in repos:
        if repo_info['GitHub'] in processed_repo_names:
            print(f"Skipping already processed repo: {repo_info['GitHub']}.")
            continue
        
        repo_name = get_repo_full_name(repo_info['GitHub'])
        repo = githubService.get_repository(repo_name)

        if repo is None:
            continue

        info = repo.to_dict()
        info = {**info, **copy_relevant_fields(repo_info)}
        checkpoint_path = repo.get_checkpoint_path()

        get_merged_prs(repo)
            
        merged_prs = csvService.read_csv(checkpoint_path)

        calculate_test_engagement_ratio(merged_prs, info)

        csvService.save_csv_row('output.csv', info)

        print(f"Processed repo: {repo_name} with score: {info['test_engagement_ratio']}.")

    print("Done processing all repositories.")