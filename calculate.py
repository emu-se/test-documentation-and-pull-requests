from dataclasses import field
import datetime
import csv
import os
import re

from github import Auth
from github import Github
from github.Repository import Repository
from github.PullRequest import PullRequest
from datetime import datetime, timezone

auth = Auth.Token("")
g = Github(auth=auth)

def get_repo_info(repo: Repository) -> dict:
    return {
        "repo_name": repo.full_name,
        "stargazers_count": repo.stargazers_count,
        "forks_count": repo.forks_count,
        "watchers_count": repo.watchers_count,
    }

def get_checkpoint_path(repo_name: str) -> str:
    repo_name = repo_name.replace('/', '_')
    return f"data/{repo_name}.csv"

def calculate_test_engagement(pr: PullRequest) -> float:
    file_extensions = ['.py', '.js', '.java', '.ts', '.tsx', '.jsx']
    files = pr.get_files()

    touches_test_files = False
    touches_production_files = False

    for f in files:
        if 'test' in f.filename.lower() or 'spec' in f.filename.lower():
            touches_test_files = True
        if any(f.filename.endswith(ext) for ext in file_extensions):
            touches_production_files = True
        if touches_test_files and touches_production_files:
            break

    return {'touches_test_files': touches_test_files, 'touches_production_files': touches_production_files}

def get_merged_prs(repo: Repository, 
                   start_date: datetime = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc), 
                   end_date: datetime = datetime(2025, 12, 1, 0, 0, tzinfo=timezone.utc)):
    
    prs = repo.get_pulls(state='closed', sort='created', direction='desc')

    repo_name = repo.full_name.replace('/', '_')
    checkpoint_path = get_checkpoint_path(repo_name)
    existing_prs = read_csv(checkpoint_path)
    existing_pr_numbers = {int(row['number']) for row in existing_prs if 'number' in row}

    for pr in prs:
        if pr.merged_at is None:
            continue
        if pr.merged_at < start_date:
            break
        if pr.number in existing_pr_numbers:
            continue
        if pr.merge_commit_sha is not None and start_date <= pr.merged_at <= end_date:
            results = calculate_test_engagement(pr)
            data = {
                    'repo_name': repo_name,
                    'number': pr.number,
                    'touches_test_files': results['touches_test_files'],
                    'touches_production_files': results['touches_production_files']
                    }
            save_csv_row(checkpoint_path, data, field_names=list(data.keys()))

def save_csv_row(path: str, 
                 info: dict, 
                 field_names: list[str] = ["repo_name", "stargazers_count", "watchers_count", "forks_count", "score"]) -> None:
    
    file_exists = os.path.isfile(path) and os.path.getsize(path) > 0
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    with open(path, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=field_names)
        if not file_exists:
            writer.writeheader()
        writer.writerow(info)

def read_csv(path: str) -> csv.DictReader:
    if not os.path.exists(path):
        return set()

    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        return [row for row in reader]
    
def get_repo_full_name(url: str) -> str:
    match = re.search(r'github\.com/([^/?]+/[^/?]+)', url)
    if match:
        return match.group(1)
    return ""

if __name__ == "__main__":
    repos = read_csv('dataset_test_documentation.csv')

    for repo_info in repos:
        repo_name = get_repo_full_name(repo_info['GitHub'])
        repo = g.get_repo(repo_name)
        info = get_repo_info(repo)
        checkpoint_path = get_checkpoint_path(repo_name)

        get_merged_prs(repo)
            
        # TODO: this might cause memory problems if there are too many PRs. might wanna lazy load this
        merged_prs = read_csv(checkpoint_path)

        count_touches_tests = sum(1 for pr in merged_prs if pr.get('touches_test_files') == 'True' and pr.get('touches_production_files') == 'True')
        count_touches_production = sum(1 for pr in merged_prs if pr.get('touches_production_files') == 'True')

        score = (count_touches_tests / count_touches_production) if count_touches_production > 0 else 0.0
        info['score'] = score

        print(f"Processed repo: {repo_name} with score: {score}. tests: {count_touches_tests} production: {count_touches_production}")
        print()

        save_csv_row('output.csv', info)

    print("Done processing all repositories.")