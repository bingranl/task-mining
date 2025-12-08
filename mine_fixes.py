import os
import json
import time
import argparse
import requests
from typing import List, Dict, Optional, Generator, Any

# GraphQL Queries
PR_QUERY = """
query ($owner: String!, $name: String!, $cursor: String, $limit: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: $limit, states: MERGED, after: $cursor, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        number
        url
        commits(first: 100) {
          pageInfo {
            hasNextPage
            endCursor
          }
          nodes {
            commit {
              oid
              message
              committedDate
              statusCheckRollup {
                state
              }
              status {
                state
              }
            }
          }
        }
      }
    }
  }
}
"""

# Additional query for fetching more commits if a PR has > 100
COMMITS_QUERY = """
query ($owner: String!, $name: String!, $pr_number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $pr_number) {
      commits(first: 100, after: $cursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          commit {
            oid
            message
            committedDate
            statusCheckRollup {
              state
            }
            status {
              state
            }
          }
        }
      }
    }
  }
}
"""

def load_env():
    """Simple .env loader to avoid external dependencies."""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

class GitHubMiner:
    def __init__(self, token: str, repo_owner: str, repo_name: str):
        self.token = token
        self.owner = repo_owner
        self.name = repo_name
        self.headers = {"Authorization": f"Bearer {token}"}
        self.api_url = "https://api.github.com/graphql"

    def _query(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a GraphQL query with retry logic."""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.api_url,
                    json={"query": query, "variables": variables},
                    headers=self.headers,
                    timeout=30
                )
                if response.status_code == 200:
                    data = response.json()
                    if "errors" in data:
                        # Handle GraphQL errors (some might be transient)
                        print(f"GraphQL Error: {data['errors']}")
                        # If it's a rate limit or server error, we might want to retry
                        # For now, just return data and let caller handle or fail
                        return data
                    return data
                elif response.status_code in [502, 503, 504, 403]:
                    wait_time = 2 ** attempt
                    print(f"API Error {response.status_code}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    response.raise_for_status()
            except requests.RequestException as e:
                wait_time = 2 ** attempt
                print(f"Request failed: {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        raise Exception("Max retries exceeded")

    def is_build_successful(self, commit_node: Dict[str, Any]) -> bool:
        """
        Determines if a commit build was successful.
        Checks both statusCheckRollup (Check Runs) and legacy status.
        """
        commit = commit_node.get("commit", {})
        
        # Priority 1: StatusCheckRollup (Modern Check Runs + Statuses)
        rollup = commit.get("statusCheckRollup")
        if rollup:
            state = rollup.get("state")
            return state == "SUCCESS"
            
        # Priority 2: Legacy Status
        status = commit.get("status")
        if status:
            state = status.get("state")
            return state == "SUCCESS"
            
        # If no status info, assume it's NOT a success (we only want proven successes)
        return False

    def is_build_failed(self, commit_node: Dict[str, Any]) -> bool:
        """
        Determines if a commit build failed.
        """
        commit = commit_node.get("commit", {})
        
        rollup = commit.get("statusCheckRollup")
        if rollup:
            state = rollup.get("state")
            return state in ["FAILURE", "ERROR"]
            
        status = commit.get("status")
        if status:
            state = status.get("state")
            return state in ["FAILURE", "ERROR"]
            
        return False

    def get_all_commits_for_pr(self, pr_node: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetches all commits for a PR, handling pagination if > 100."""
        commits_data = pr_node["commits"]
        all_commits = commits_data["nodes"]
        
        page_info = commits_data["pageInfo"]
        cursor = page_info["endCursor"]
        has_next = page_info["hasNextPage"]
        pr_number = pr_node["number"]

        while has_next:
            print(f"Fetching more commits for PR #{pr_number}...")
            variables = {
                "owner": self.owner,
                "name": self.name,
                "pr_number": pr_number,
                "cursor": cursor
            }
            data = self._query(COMMITS_QUERY, variables)
            pr_data = data["data"]["repository"]["pullRequest"]
            new_commits = pr_data["commits"]
            
            all_commits.extend(new_commits["nodes"])
            
            page_info = new_commits["pageInfo"]
            cursor = page_info["endCursor"]
            has_next = page_info["hasNextPage"]
            
        return all_commits

    def mine(self, limit: int) -> List[Dict[str, Any]]:
        """Mines the repository for Bad -> Good commit pairs."""
        results = []
        cursor = None
        processed_count = 0
        
        while processed_count < limit:
            batch_size = min(50, limit - processed_count)
            variables = {
                "owner": self.owner,
                "name": self.name,
                "cursor": cursor,
                "limit": batch_size
            }
            
            print(f"Fetching PRs (cursor={cursor})...")
            data = self._query(PR_QUERY, variables)
            
            if not data.get("data") or not data["data"].get("repository"):
                print("No data returned or repository not found.")
                break

            prs = data["data"]["repository"]["pullRequests"]
            nodes = prs["nodes"]
            
            for pr in nodes:
                pr_number = pr["number"]
                commits = self.get_all_commits_for_pr(pr)
                
                # Sort commits by date just in case, though GraphQL usually returns ordered
                # But we requested DESC in PRs, commits inside PR are usually ASC?
                # Let's verify order. The default order for commits connection is usually ASC.
                # We'll assume ASC (oldest first) for logic "Bad -> Good".
                
                # Logic: Find a Bad commit, then look for a subsequent Good commit.
                # We iterate through commits.
                
                last_bad_commit = None
                
                for commit_node in commits:
                    commit = commit_node["commit"]
                    oid = commit["oid"]
                    msg = commit["message"].split('\n')[0] # First line only
                    
                    if self.is_build_failed(commit_node):
                        last_bad_commit = commit_node
                    elif self.is_build_successful(commit_node):
                        if last_bad_commit:
                            # Found a pair!
                            bad_commit = last_bad_commit["commit"]
                            pair = {
                                "pr_id": pr_number,
                                "pr_url": pr["url"],
                                "bad_commit": bad_commit["oid"],
                                "bad_msg": bad_commit["message"].split('\n')[0],
                                "good_commit": oid,
                                "good_msg": msg
                            }
                            results.append(pair)
                            print(f"Found pair in PR #{pr_number}: {bad_commit['oid'][:7]} (Bad) -> {oid[:7]} (Good)")
                            
                            # Reset last_bad_commit to avoid pairing the same bad commit with multiple good ones?
                            # Or should we? Usually one fix is enough.
                            # Let's reset to capture distinct pairs.
                            last_bad_commit = None
            
            processed_count += len(nodes)
            cursor = prs["pageInfo"]["endCursor"]
            if not prs["pageInfo"]["hasNextPage"]:
                break
                
        return results

def main():
    load_env()
    
    parser = argparse.ArgumentParser(description="Mine Self-Correction Pairs from GitHub")
    parser.add_argument("repo", help="GitHub repository in 'owner/name' format")
    parser.add_argument("--token", help="GitHub PAT (optional if GITHUB_TOKEN env var is set)")
    parser.add_argument("--limit", type=int, default=100, help="Number of PRs to scan")
    parser.add_argument("--output", default="mining_results.json", help="Output JSON file")
    
    args = parser.parse_args()
    
    token = args.token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: No GitHub token provided. Set GITHUB_TOKEN or use --token.")
        return

    if "/" not in args.repo:
        print("Error: Repo must be in 'owner/name' format.")
        return
        
    owner, name = args.repo.split("/", 1)
    
    miner = GitHubMiner(token, owner, name)
    print(f"Mining {args.repo} for up to {args.limit} PRs...")
    
    results = miner.mine(args.limit)
    
    print(f"Mining complete. Found {len(results)} pairs.")
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {args.output}")

if __name__ == "__main__":
    main()
