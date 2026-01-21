#!/usr/bin/env python3
"""
Generate verification tests for build script changes using LLM or templates.

This script takes a candidate pair (O, M) and generates Gradle Test Kit tests
that fail on O and pass on M.
"""

import json
import argparse
import sys
import os
from cmath import inf
from pathlib import Path
import requests
from litellm import completion


def load_prompt_template():
    """Load the LLM prompt template."""
    prompt_path = Path(__file__).parent / 'prompts' / 'gradle_test_generation.txt'
    with open(prompt_path, 'r') as f:
        return f.read()


def get_commit_diff(repo_url, bad_commit, good_commit, file_path):
    """
    Fetch the diff for a specific file between two commits.
    
    Args:
        repo_url: GitHub repo URL (e.g., https://github.com/android/nowinandroid)
        bad_commit: Bad commit SHA
        good_commit: Good commit SHA
        file_path: Path to the file in the repo
    
    Returns:
        Diff string or None if failed
    """
    parts = repo_url.rstrip('/').split('/')
    owner, repo = parts[-2], parts[-1]

    # GitHub API endpoint for comparing commits
    api_url = f"https://api.github.com/repos/{owner}/{repo}/compare/{bad_commit}...{good_commit}"

    headers = {}
    github_token = os.environ.get('GITHUB_TOKEN')
    if github_token:
        headers['Authorization'] = f'token {github_token}'

    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        data = response.json()

        # Find the file in the diff
        for file_data in data.get('files', []):
            if file_data['filename'] == file_path:
                return file_data.get('patch', '')

        return None
    except Exception as e:
        print(f"Error fetching diff: {e}", file=sys.stderr)
        return None


def get_file_content(repo_url, commit_sha, file_path):
    """
    Fetch the content of a specific file at a given commit.
    
    Args:
        repo_url: GitHub repo URL (e.g., https://github.com/android/nowinandroid)
        commit_sha: Commit SHA
        file_path: Path to the file in the repo
    
    Returns:
        File content as string or None if failed
    """
    parts = repo_url.rstrip('/').split('/')
    owner, repo = parts[-2], parts[-1]

    # GitHub API endpoint for file content at specific commit
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}?ref={commit_sha}"

    headers = {}
    github_token = os.environ.get('GITHUB_TOKEN')
    if github_token:
        headers['Authorization'] = f'token {github_token}'

    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        data = response.json()

        # Decode base64 content
        import base64
        content = base64.b64decode(data['content']).decode('utf-8')
        return content
    except Exception as e:
        print(f"Error fetching file content from {commit_sha}: {e}", file=sys.stderr)
        return None


def generate_test_with_llm(task_description, diff, api_key=None):
    """
    Generate test using LLM via litellm.
    
    Args:
        task_description: Description of the task/fix
        diff: The build script diff
        api_key: Litellm API key (optional, can use LITELLM_API_KEY env var)
    
    Returns:
        Generated test code or None
    """
    if api_key:
        os.environ['LITELLM_API_KEY'] = api_key

    if not os.environ.get('LITELLM_API_KEY'):
        print("Warning: No LITELLM_API_KEY found. Skipping LLM generation.", file=sys.stderr)
        return None

    litellm_base_url = os.environ.get('LITE_LLM_URL') or os.environ.get('LITELLM_BASE_URL')

    prompt_template = load_prompt_template()
    prompt = prompt_template.replace('{task_description}', task_description).replace('{diff}', diff)

    try:
        model = os.environ.get('LLM_MODEL', 'anthropic/claude-sonnet-4-5')

        # Prepare completion arguments
        completion_args = {
            'model': model,
            'messages': [{"role": "user", "content": prompt}]
        }

        # Add base_url and api_key if custom URL is provided
        if litellm_base_url:
            completion_args['base_url'] = litellm_base_url
            completion_args['api_key'] = os.environ.get('LITELLM_API_KEY')

        response = completion(**completion_args)
        text = response.choices[0].message.content

        # Extract Java code from markdown if present
        if '```java' in text:
            start = text.find('```java') + 7
            end = text.find('```', start)
            return text[start:end].strip()
        elif '```' in text:
            start = text.find('```') + 3
            end = text.find('```', start)
            return text[start:end].strip()
        else:
            return text.strip()

    except Exception as e:
        print(f"Error calling LLM via litellm: {e}", file=sys.stderr)
        return None


def generate_test_from_template(change_type, diff):
    """
    Generate test using predefined templates.
    
    Args:
        change_type: Type of change (dependency, task, plugin, etc.)
        diff: The build script diff
    
    Returns:
        Generated test code
    """
    # Simple template-based generation
    # This is a fallback when LLM is not available

    template = """
import org.gradle.testkit.runner.BuildResult;
import org.gradle.testkit.runner.GradleRunner;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.*;

public class BuildScriptVerificationTest {
    
    @TempDir
    Path tempDir;
    
    private File projectDir;
    
    @BeforeEach
    public void setup() {
        projectDir = tempDir.toFile();
    }
    
    @Test
    public void testBuildScriptChange() {
        // TODO: Implement specific verification based on the change
        // This is a template - customize based on actual change type
        
        BuildResult result = GradleRunner.create()
            .withProjectDir(projectDir)
            .withArguments("tasks")
            .build();
        
        assertNotNull(result);
    }
}
"""
    return template


def generate_sample(candidate, output_dir, use_llm=True):
    """
    Generate a complete sample for a candidate.
    
    Args:
        candidate: Candidate dict with PR and commit info
        output_dir: Output directory for the samples
        use_llm: Whether to use LLM for test generation
    """
    pr_id = candidate['pr_id']
    sample_name = f"{pr_id}_{candidate['bad_commit'][:7]}"
    sample_dir = Path(output_dir) / sample_name

    # Create directory structure
    (sample_dir / 'original').mkdir(parents=True, exist_ok=True)
    (sample_dir / 'modified').mkdir(parents=True, exist_ok=True)
    (sample_dir / 'verification').mkdir(parents=True, exist_ok=True)

    # Create task description
    task_desc = f"""# Task Description

**PR**: {candidate['pr_url']}

## Bad Commit
- SHA: {candidate['bad_commit']}
- Message: {candidate['bad_msg']}

## Good Commit
- SHA: {candidate['good_commit']}
- Message: {candidate['good_msg']}

## Files Changed
{chr(10).join('- ' + f for f in candidate.get('build_files_changed', []))}

## Category
{candidate.get('category', 'Unknown')}

## Objective
Fix the build script issue identified in the bad commit.
"""

    with open(sample_dir / 'task_description.md', 'w') as f:
        f.write(task_desc)

    # Try to fetch and generate test
    if candidate.get('build_files_changed'):
        # Get the first build file (for simplicity in POC)
        build_file = candidate['build_files_changed'][0]

        # Extract repo URL from PR URL
        repo_url = '/'.join(candidate['pr_url'].split('/')[:5])

        # Fetch diff
        diff = get_commit_diff(
            repo_url,
            candidate['bad_commit'],
            candidate['good_commit'],
            build_file
        )

        if diff and use_llm:
            # Generate test with LLM
            test_code = generate_test_with_llm(task_desc, diff)

            if test_code:
                with open(sample_dir / 'verification' / 'BuildScriptTest.java', 'w') as f:
                    f.write(test_code)
                print(f"✓ Generated LLM test for {sample_name}")
            else:
                # Fallback to template
                test_code = generate_test_from_template('generic', diff)
                with open(sample_dir / 'verification' / 'BuildScriptTest.java', 'w') as f:
                    f.write(test_code)
                print(f"⚠ Generated template test for {sample_name} (LLM failed)")
        else:
            # Use template
            test_code = generate_test_from_template('generic', diff or '')
            with open(sample_dir / 'verification' / 'BuildScriptTest.java', 'w') as f:
                f.write(test_code)
            print(f"⚠ Generated template test for {sample_name} (no diff or LLM disabled)")

    # Fetch and write actual build scripts from commits
    if candidate.get('build_files_changed'):
        build_file = candidate['build_files_changed'][0]
        repo_url = '/'.join(candidate['pr_url'].split('/')[:5])
        
        # Fetch original (bad) build script
        original_content = get_file_content(repo_url, candidate['bad_commit'], build_file)
        with open(sample_dir / 'original' / 'build.gradle.kts', 'w') as f:
            if original_content:
                f.write(original_content)
            else:
                f.write(f"// Original build script from commit {candidate['bad_commit']}\n")
                f.write(f"// Failed to fetch content from GitHub for {build_file}\n")
        
        # Fetch modified (good) build script
        modified_content = get_file_content(repo_url, candidate['good_commit'], build_file)
        with open(sample_dir / 'modified' / 'build.gradle.kts', 'w') as f:
            if modified_content:
                f.write(modified_content)
            else:
                f.write(f"// Modified build script from commit {candidate['good_commit']}\n")
                f.write(f"// Failed to fetch content from GitHub for {build_file}\n")
    else:
        # No build files changed - write placeholders
        with open(sample_dir / 'original' / 'build.gradle.kts', 'w') as f:
            f.write(f"// Original build script from commit {candidate['bad_commit']}\n")
            f.write("// No build files changed in this candidate\n")
        
        with open(sample_dir / 'modified' / 'build.gradle.kts', 'w') as f:
            f.write(f"// Modified build script from commit {candidate['good_commit']}\n")
            f.write("// No build files changed in this candidate\n")

    return sample_dir


def main():
    parser = argparse.ArgumentParser(
        description='Generate verification tests for build script changes'
    )
    parser.add_argument(
        '--candidates',
        default='swe-bench-poc/data/candidates.json',
        help='Path to candidates.json'
    )
    parser.add_argument(
        '--output',
        default='swe-bench-poc/data/samples',
        help='Output directory for samples'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=+inf,
        help='Maximum number of samples to generate'
    )
    parser.add_argument(
        '--no-llm',
        action='store_true',
        help='Disable LLM-based generation, use templates only'
    )

    args = parser.parse_args()

    # Load candidates
    if not Path(args.candidates).exists():
        print(f"Error: Candidates file not found: {args.candidates}", file=sys.stderr)
        print("Run extract_build_changes.py first to generate candidates.", file=sys.stderr)
        sys.exit(1)

    with open(args.candidates, 'r') as f:
        candidates = json.load(f)

    # Filter candidates with build file changes
    valid_candidates = [c for c in candidates if c.get('build_files_changed')]

    if not valid_candidates:
        print("No valid candidates with build file changes found.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(valid_candidates)} valid candidates")
    print(f"Generating up to {args.limit} samples...")

    # Generate samples
    use_llm = not args.no_llm
    for i, candidate in enumerate(valid_candidates[:args.limit]):
        print(f"\n[{i + 1}/{min(args.limit, len(valid_candidates))}] Processing PR #{candidate['pr_id']}...")
        generate_sample(candidate, args.output, use_llm=use_llm)

    print(f"\n✓ Sample generation complete!")
    print(f"Output directory: {args.output}")


if __name__ == '__main__':
    main()
