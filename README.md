# Task Mining: Self-Correction Pairs

This project mines GitHub repositories for "Self-Correction" pairs (Bad Commit -> Good Commit) in merged Pull Requests. It specifically looks for build failures followed by fixes.

## Scripts

### 0. `run_pipeline.py` (The All-in-One)
**Function**: Runs the entire pipeline (Mining -> Analysis -> AI).
- **Usage (Single Repo)**:
  ```bash
  python3 run_pipeline.py android/nowinandroid --limit 100
  ```
- **Usage (Multi-Repo)**:
  Create a file `repos.txt` with one repo per line, then:
  ```bash
  python3 run_pipeline.py repos.txt --limit 100
  ```
  Results will be saved in `results/{owner}_{name}/`.

### 1. `mine_fixes.py` (The Miner)
**Function**: Identifies "Self-Correction" pairs in merged PRs.
- **Logic**: Scans PRs for a sequence of `Failure -> Success` commits.
- **Input**: GitHub Repo (owner/name)
- **Output**: `mining_results.json`
- **Usage**:
  ```bash
  python3 mine_fixes.py android/nowinandroid --limit 100
  ```

### 2. `analyze_pairs.py` (The Heuristic Classifier)
**Function**: Classifies pairs based on changed files (Fast & Cheap).
- **Logic**: Checks if `build.gradle`, `libs.versions.toml`, or other build files were modified.
- **Categories**: `Dependency Update` vs `Other`.
- **Input**: `mining_results.json`
- **Output**: `analyzed_results.json`
- **Usage**:
  ```bash
  python3 analyze_pairs.py android/nowinandroid
  ```

### 3. `gemini_classifier.py` (The AI Classifier)
**Function**: Classifies pairs using an LLM (Gemini) for deeper understanding.
- **Logic**: Fetches the actual code diff and asks Gemini: "Is this a dependency update?".
- **Benefit**: Can distinguish between a simple version bump and a logic fix in a build file.
- **Input**: `analyzed_results.json`
- **Output**: `ai_classified_results.json`
- **Usage**:
  ```bash
  python3 gemini_classifier.py android/nowinandroid
  ```

## Resumability
Both `mine_fixes.py` and `gemini_classifier.py` support resuming if interrupted.

- **Mining**: Uses a state file (default `mining_state.json`) to save the cursor.
  - To resume: Just run the same command again.
  - To restart: Delete `mining_state.json` and `mining_results.json`.

- **AI Classification**: Checks `ai_classified_results.json` for existing entries.
  - To resume: Run the command again; it skips already classified pairs.
  - To restart: Delete `ai_classified_results.json`.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install requests
    ```
2.  **Environment Variables**:
    Create a `.env` file:
    ```env
    GITHUB_TOKEN=your_github_pat
    GEMINI_API_KEY=your_gemini_key
    ```
