# Usage Guide

This guide walks you through using the SWE-bench-like benchmark generation POC.

## Prerequisites

- Python 3.8+
- Java 17+
- Gradle 8.0+ (or use the wrapper)
- GitHub API token (optional, for fetching diffs)
- LiteLLM API key (optional, for LLM-based test generation)

## Quick Start

### 1. Extract Build Script Changes

Extract candidate pairs from the mining results:

```bash
python swe-bench-poc/extract_build_changes.py \
  --input mining_results.json \
  --analyzed analyzed_results.json \
  --output swe-bench-poc/data/candidates.json
```

**Output:**
```
Total pairs extracted: 150
Pairs with confirmed build script changes: 45
Output saved to: candidates.json
```

### 2. Generate Samples

Generate samples automatically using LLM or templates:

```bash
python swe-bench-poc/generator/test_generator.py --limit 5
```

**Options:**
- `--no-llm`: Disable LLM generation, use templates only
- `--limit N`: Generate at most N samples

### 3. Verify Samples

Verify all samples in the samples directory by running verification tests:

```bash
python swe-bench-poc/runner/verify.py
```

**Options:**
- `--samples-dir PATH`: Path to samples directory (default: `swe-bench-poc/data/samples`)
- `--verbose`: Show detailed output for each sample verification

**Expected Output:**
```
Scanning for samples in: /path/to/swe-bench-poc/data/samples
Found 3 valid sample(s)

================================================================================

[1/3] Verifying: sample_1913_149a345
--------------------------------------------------------------------------------
Verification: SUCCESS ✓✓✓

[2/3] Verifying: sample_1930_c48c838
--------------------------------------------------------------------------------
Verification: SUCCESS ✓✓✓

[3/3] Verifying: sample_2003_92fd6f6
--------------------------------------------------------------------------------
Verification: SUCCESS ✓✓✓

================================================================================
VERIFICATION SUMMARY
================================================================================

Total samples: 3
Successful:    3 ✓
Failed:        0 ✗

  ✓ PASS  sample_1913_149a345
  ✓ PASS  sample_1930_c48c838
  ✓ PASS  sample_2003_92fd6f6

All samples passed verification!
```

**To verify a single sample:**
```bash
python swe-bench-poc/runner/verify_sample.py swe-bench-poc/data/samples/example_1_dependency_update
```

## Integration with Mining Pipeline

Integrate with the existing task-mining workflow:

```bash
# 1. Mine repositories
python mine_fixes.py android/nowinandroid --limit 100

# 2. Analyze pairs
python analyze_pairs.py android/nowinandroid

# 3. Extract build changes
python swe-bench-poc/data/extract_build_changes.py

# 4. Generate samples
python swe-bench-poc/generator/test_generator.py --limit 10

# 5. Verify samples
python swe-bench-poc/runner/verify.py
```

## Gradle Test Kit Patterns

### Pattern 1: Verify Dependency Version

```java
@Test
public void testDependencyVersion() {
    BuildResult result = GradleRunner.create()
        .withProjectDir(projectDir)
        .withArguments("dependencies", "--configuration", "implementation")
        .build();
    
    assertTrue(result.getOutput().contains("com.example:lib:2.0.0"));
}
```

### Pattern 2: Verify Task Exists

```java
@Test
public void testTaskExists() {
    BuildResult result = GradleRunner.create()
        .withProjectDir(projectDir)
        .withArguments("tasks", "--all")
        .build();
    
    assertTrue(result.getOutput().contains("myCustomTask"));
}
```

### Pattern 3: Verify Build Success

```java
@Test
public void testBuildSucceeds() {
    BuildResult result = GradleRunner.create()
        .withProjectDir(projectDir)
        .withArguments("build")
        .build();
    
    assertEquals(TaskOutcome.SUCCESS, result.task(":build").getOutcome());
}
```

### Pattern 4: Verify Plugin Application

```java
@Test
public void testPluginApplied() {
    BuildResult result = GradleRunner.create()
        .withProjectDir(projectDir)
        .withArguments("plugins")
        .build();
    
    assertTrue(result.getOutput().contains("com.example.plugin"));
}
```

## Environment Variables

Set these in your `.env` file or shell:

```bash
# For fetching diffs from GitHub
export GITHUB_TOKEN=your_github_personal_access_token

# For LLM-based test generation
export LITE_LLM_URL=...
export  LITELLM_API_KEY=...
```

## Tips for Writing Good Verification Tests

1. **Be Specific:** Test the exact change, not general build success
2. **Use Assertions:** Include clear assertion messages
3. **Keep it Simple:** One test per specific aspect of the change
4. **Make it Deterministic:** Avoid flaky tests that depend on timing or external state
5. **Document Intent:** Add comments explaining what each test verifies
