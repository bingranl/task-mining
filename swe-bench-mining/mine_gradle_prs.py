"""
Script to mine PRs with gradle build changes from multiple repositories.
Outputs data in SWE-bench format.

This script:
1. Processes multiple repositories from dataset_repos.json
2. Finds PRs that contain gradle build changes (libs.versions.toml, build.gradle, build.gradle.kts)
3. Extracts the base commit (commit before the PR)
4. Outputs in SWE-bench format
"""

import argparse
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
from dotenv import load_dotenv


class GradlePRMiner:
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.api_url = "https://api.github.com"

    def get_pr_files(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        url = f"{self.api_url}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to fetch PR files {owner}/{repo}#{pr_number}: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error fetching PR files {owner}/{repo}#{pr_number}: {e}")
            return []

    def get_pr_details(self, owner: str, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        url = f"{self.api_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to fetch PR details {owner}/{repo}#{pr_number}: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error fetching PR details {owner}/{repo}#{pr_number}: {e}")
            return None

    def get_pr_commits(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        url = f"{self.api_url}/repos/{owner}/{repo}/pulls/{pr_number}/commits"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to fetch PR commits {owner}/{repo}#{pr_number}: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error fetching PR commits {owner}/{repo}#{pr_number}: {e}")
            return []

    def get_commit_details(self, owner: str, repo: str, commit_sha: str) -> Optional[Dict[str, Any]]:
        url = f"{self.api_url}/repos/{owner}/{repo}/commits/{commit_sha}"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to fetch commit {owner}/{repo}@{commit_sha}: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error fetching commit {owner}/{repo}@{commit_sha}: {e}")
            return None

    def has_gradle_changes(self, files: List[Dict[str, Any]]) -> bool:
        for file in files:
            filename = file.get('filename', '')
            if ("libs.versions.toml" in filename or
                    filename.endswith("build.gradle") or
                    filename.endswith("build.gradle.kts")):
                return True
        return False

    def get_base_commit(self, owner: str, repo: str, pr_number: int) -> Optional[str]:
        commits = self.get_pr_commits(owner, repo, pr_number)
        if not commits:
            return None

        first_commit_sha = commits[0]['sha']

        commit_details = self.get_commit_details(owner, repo, first_commit_sha)
        if not commit_details:
            return None

        parents = commit_details.get('parents', [])
        if parents:
            return parents[0]['sha']

        return None

    def get_pr_patch(self, owner: str, repo: str, pr_number: int) -> str:
        url = f"{self.api_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        headers = {**self.headers, "Accept": "application/vnd.github.v3.diff"}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.text
            else:
                print(f"Failed to fetch PR patch {owner}/{repo}#{pr_number}: {response.status_code}")
                return ""
        except Exception as e:
            print(f"Error fetching PR patch {owner}/{repo}#{pr_number}: {e}")
            return ""

    def filter_gradle_patch(self, patch: str) -> str:
        """Filter patch to only include gradle-related files."""
        if not patch:
            return ""

        lines = patch.split('\n')
        filtered_lines = []
        include_current_file = False
        file_header_lines = []

        for line in lines:
            # Check if this is a file header (diff --git a/... b/...)
            if line.startswith('diff --git'):
                # Save previous file if it should be included
                if include_current_file and file_header_lines:
                    filtered_lines.extend(file_header_lines)

                # Start new file section
                file_header_lines = [line]
                include_current_file = False

                # Extract filename from diff header
                parts = line.split()
                if len(parts) >= 4:
                    # Format: diff --git a/path/to/file b/path/to/file
                    filename = parts[2][2:]  # Remove 'a/' prefix
                    if ("libs.versions.toml" in filename or
                            filename.endswith("build.gradle") or
                            filename.endswith("build.gradle.kts")):
                        include_current_file = True
            else:
                file_header_lines.append(line)

        if include_current_file and file_header_lines:
            filtered_lines.extend(file_header_lines)

        return '\n'.join(filtered_lines)

    def process_pr(self, owner: str, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        files = self.get_pr_files(owner, repo, pr_number)
        if not files:
            return None

        if not self.has_gradle_changes(files):
            return None

        pr_details = self.get_pr_details(owner, repo, pr_number)
        if not pr_details:
            return None

        base_commit = self.get_base_commit(owner, repo, pr_number)
        if not base_commit:
            print(f"Warning: Could not determine base commit for {owner}/{repo}#{pr_number}")
            return None

        patch = self.get_pr_patch(owner, repo, pr_number)
        patch = self.filter_gradle_patch(patch)

        instance_id = f"{owner}__{repo.replace('/', '_')}-{pr_number}"

        swe_bench_entry = {
            "instance_id": instance_id,
            "repo": f"{owner}/{repo}",
            "issue_id": pr_number,
            "base_commit": base_commit,
            "problem_statement": pr_details.get('title', ''),
            "version": "1.0.0",
            "issue_url": "",
            "pr_url": pr_details.get('html_url', ''),
            "patch": patch,
            "test_patch": "",
            "created_at": pr_details.get('created_at', ''),
            "FAIL_TO_PASS": [],
            "PASS_TO_PASS": []
        }

        return swe_bench_entry

    def search_gradle_prs(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        url = f"{self.api_url}/repos/{owner}/{repo}/pulls"

        all_prs = []
        page = 1
        per_page = 100  # GitHub API maximum

        try:
            while True:
                params = {
                    "state": "closed",
                    "per_page": per_page,
                    "page": page,
                    "sort": "updated",
                    "direction": "desc"
                }

                response = requests.get(url, headers=self.headers, params=params, timeout=10)
                if response.status_code != 200:
                    print(f"Failed to fetch PRs for {owner}/{repo} (page {page}): {response.status_code}")
                    break

                prs = response.json()

                # If no PRs returned, we've reached the end
                if not prs:
                    break

                all_prs.extend(prs)
                print(f"Fetched page {page}: {len(prs)} PRs from {owner}/{repo}")

                # If we got fewer PRs than per_page, this is the last page
                if len(prs) < per_page:
                    break

                page += 1

            merged_prs = [pr for pr in all_prs if pr.get('merged_at')]

            print(f"Found {len(merged_prs)} merged PRs (out of {len(all_prs)} total) in {owner}/{repo}, processing...")

            results = []
            for pr in merged_prs:
                pr_number = pr['number']
                result = self.process_pr(owner, repo, pr_number)
                if result:
                    results.append(result)
                    print(f"  ✓ {owner}/{repo}#{pr_number} - {result['problem_statement'][:60]}")

            return results

        except Exception as e:
            print(f"Error searching PRs for {owner}/{repo}: {e}")
            return []

    def process_repository(self, repo_full_name: str) -> List[Dict[str, Any]]:
        parts = repo_full_name.split('/')
        if len(parts) != 2:
            print(f"Invalid repository format: {repo_full_name}")
            return []

        owner, repo = parts
        print(f"\nProcessing repository: {owner}/{repo}")

        return self.search_gradle_prs(owner, repo)

    def mine_all_repos(self, repos: List[str], output_file: str, max_workers: int = 3):
        file_lock = threading.Lock()

        existing_results = []
        processed_repos = set()

        if os.path.exists(output_file):
            try:
                with open(output_file, 'r') as f:
                    existing_results = json.load(f)
                    for entry in existing_results:
                        repo = entry.get('repo')
                        if repo:
                            processed_repos.add(repo)
                print(
                    f"Found existing results with {len(existing_results)} entries from {len(processed_repos)} repositories")
                print(f"Skipping already processed repositories: {sorted(processed_repos)}")
            except Exception as e:
                print(f"Warning: Could not load existing results: {e}")
                existing_results = []
                processed_repos = set()

        repos_to_process = [repo for repo in repos if repo not in processed_repos]

        if not repos_to_process:
            print("All repositories have already been processed!")
            return

        if not existing_results:
            with open(output_file, 'w') as f:
                json.dump([], f)

        print(f"Mining {len(repos_to_process)} repositories (skipping {len(processed_repos)} already processed)...")

        total_count = len(existing_results)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_repo = {
                executor.submit(self.process_repository, repo): repo
                for repo in repos_to_process
            }

            for future in as_completed(future_to_repo):
                repo = future_to_repo[future]
                try:
                    results = future.result()

                    if results:
                        with file_lock:
                            with open(output_file, 'r') as f:
                                all_results = json.load(f)

                            all_results.extend(results)

                            with open(output_file, 'w') as f:
                                json.dump(all_results, f, indent=2)

                            total_count += len(results)

                    print(f"Completed {repo}: found {len(results)} PRs with gradle changes")
                except Exception as e:
                    print(f"Failed to process {repo}: {e}")

        print(f"\n{'=' * 60}")
        print(f"Mining complete!")
        print(f"Total PRs with gradle changes: {total_count}")
        print(f"Results saved to: {output_file}")
        print(f"{'=' * 60}")


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Mine PRs with gradle build changes from multiple repositories"
    )
    parser.add_argument(
        "--repos",
        default="dataset_repos.json",
        help="JSON file containing list of repositories (default: dataset_repos.json)"
    )
    parser.add_argument(
        "--output",
        default="gradle_prs_swe_bench.json",
        help="Output file for SWE-bench format results (default: gradle_prs_swe_bench.json)"
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=3,
        help="Number of concurrent workers (default: 3)"
    )

    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN not set. Please set it in .env file or environment.")
        return

    repos_file = Path(args.repos)
    if not repos_file.exists():
        print(f"Error: Repository list file not found: {args.repos}")
        return

    with open(repos_file, 'r') as f:
        repos = json.load(f)

    if not repos:
        print("Error: No repositories found in the input file.")
        return

    miner = GradlePRMiner(token)
    miner.mine_all_repos(repos, args.output, args.max_workers)


if __name__ == "__main__":
    main()
