#!/usr/bin/env python3
"""
Extract build script change pairs from mining results.

This script filters the mining results to find pairs where build scripts
(build.gradle, build.gradle.kts, libs.versions.toml, etc.) were modified.
These pairs are candidates for SWE-bench-like sample generation.
"""

import json
import argparse
import sys
from pathlib import Path


BUILD_SCRIPT_PATTERNS = [
    'build.gradle',
    'build.gradle.kts',
    'settings.gradle',
    'settings.gradle.kts',
    'libs.versions.toml',
    'gradle.properties',
    'gradle-wrapper.properties',
]


def is_build_script_file(filename):
    """Check if a file is a build script."""
    filename_lower = filename.lower()
    
    # Check exact matches
    for pattern in BUILD_SCRIPT_PATTERNS:
        if filename_lower.endswith(pattern):
            return True
    
    # Check for build-logic or buildSrc directories
    if 'build-logic' in filename or 'buildsrc' in filename_lower:
        if filename.endswith('.kt') or filename.endswith('.kts') or filename.endswith('.gradle'):
            return True
    
    return False


def extract_build_changes(input_file, output_file, analyzed_file=None):
    """
    Extract pairs where build scripts were changed.
    
    Args:
        input_file: Path to mining_results.json
        output_file: Path to output candidates.json
        analyzed_file: Optional path to analyzed_results.json for file change info
    """
    # Load mining results
    with open(input_file, 'r') as f:
        mining_results = json.load(f)
    
    # Load analyzed results if available (contains files_changed)
    analyzed_map = {}
    if analyzed_file and Path(analyzed_file).exists():
        with open(analyzed_file, 'r') as f:
            analyzed_results = json.load(f)
            for item in analyzed_results:
                key = (item['pr_id'], item['bad_commit'], item['good_commit'])
                analyzed_map[key] = item
    
    candidates = []
    
    for item in mining_results:
        pr_id = item['pr_id']
        bad_commit = item['bad_commit']
        good_commit = item['good_commit']
        
        # Check if we have analyzed data with file changes
        key = (pr_id, bad_commit, good_commit)
        if key in analyzed_map:
            analyzed_item = analyzed_map[key]
            files_changed = analyzed_item.get('files_changed', [])
            
            # Check if any build script was changed
            build_files = [f for f in files_changed if is_build_script_file(f)]
            
            if build_files:
                candidate = {
                    'pr_id': pr_id,
                    'pr_url': item['pr_url'],
                    'bad_commit': bad_commit,
                    'bad_msg': item['bad_msg'],
                    'good_commit': good_commit,
                    'good_msg': item['good_msg'],
                    'build_files_changed': build_files,
                    'all_files_changed': files_changed,
                    'category': analyzed_item.get('category', 'Unknown')
                }
                candidates.append(candidate)
        else:
            # No analyzed data, include all pairs (will need manual filtering)
            candidate = {
                'pr_id': pr_id,
                'pr_url': item['pr_url'],
                'bad_commit': bad_commit,
                'bad_msg': item['bad_msg'],
                'good_commit': good_commit,
                'good_msg': item['good_msg'],
                'build_files_changed': None,  # Unknown
                'all_files_changed': None,
                'category': 'Unknown'
            }
            candidates.append(candidate)
    
    # Save candidates
    with open(output_file, 'w') as f:
        json.dump(candidates, f, indent=2)
    
    # Print statistics
    total = len(candidates)
    with_build_files = len([c for c in candidates if c['build_files_changed']])
    
    print(f"Total pairs extracted: {total}")
    print(f"Pairs with confirmed build script changes: {with_build_files}")
    print(f"Output saved to: {output_file}")
    
    if with_build_files > 0:
        print("\nBuild file types found:")
        file_types = {}
        for candidate in candidates:
            if candidate['build_files_changed']:
                for f in candidate['build_files_changed']:
                    ext = Path(f).name
                    file_types[ext] = file_types.get(ext, 0) + 1
        
        for file_type, count in sorted(file_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  {file_type}: {count}")


def main():
    parser = argparse.ArgumentParser(
        description='Extract build script change pairs from mining results'
    )
    parser.add_argument(
        '--input',
        default='../mining_results.json',
        help='Path to mining_results.json (default: ../mining_results.json)'
    )
    parser.add_argument(
        '--analyzed',
        default='../analyzed_results.json',
        help='Path to analyzed_results.json (default: ../analyzed_results.json)'
    )
    parser.add_argument(
        '--output',
        default='candidates.json',
        help='Output file for candidates (default: candidates.json)'
    )
    
    args = parser.parse_args()
    
    if not Path(args.input).exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    extract_build_changes(args.input, args.output, args.analyzed)


if __name__ == '__main__':
    main()
