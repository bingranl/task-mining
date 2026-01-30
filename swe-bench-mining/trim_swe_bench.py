import json

# Load the JSON file
with open('gradle_prs_swe_bench.json', 'r') as f:
    data = json.load(f)

print(f"Total instances: {len(data)}")

# Get unique repositories and keep first instance per repo
repos = {}
for instance in data:
    repo = instance['repo']
    if repo not in repos:
        repos[repo] = instance

print(f"Unique repositories: {len(repos)}")
print("\nRepositories found:")
for repo in sorted(repos.keys()):
    print(f"  - {repo}")

# Create trimmed dataset with one instance per repo
trimmed_data = [repos[repo] for repo in sorted(repos.keys())]

# Save to new file
output_file = 'gradle_prs_swe_bench_trimmed.json'
with open(output_file, 'w') as f:
    json.dump(trimmed_data, f, indent=2)

print(f"\nTrimmed dataset saved to: {output_file}")
print(f"Trimmed dataset size: {len(trimmed_data)} instances")
