#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path
from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from verify_sample import verify_sample


def find_samples(samples_dir: Path) -> List[Path]:
    """Find all valid sample directories with required structure."""
    if not samples_dir.exists() or not samples_dir.is_dir():
        return []

    valid_samples = []
    for item in sorted(samples_dir.iterdir()):
        if not item.is_dir():
            continue

        # Check required files exist
        has_original = (item / "original" / "build.gradle.kts").exists()
        has_modified = (item / "modified" / "build.gradle.kts").exists()
        verification_dir = item / "verification"
        has_tests = verification_dir.is_dir() and any(verification_dir.glob("*.java"))

        if has_original and has_modified and has_tests:
            valid_samples.append(item)

    return valid_samples


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify all samples in the data/samples directory by running verification tests."
    )
    parser.add_argument(
        "--samples-dir",
        type=str,
        default=None,
        help="Path to samples directory (default: ../data/samples relative to this script)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output for each sample verification"
    )
    args = parser.parse_args()

    # Determine paths
    script_dir = Path(__file__).resolve().parent
    samples_dir = Path(args.samples_dir).resolve() if args.samples_dir else (
            script_dir.parent / "data" / "samples").resolve()
    framework_src = (script_dir.parent / "gradle-testkit-framework").resolve()

    # Validate paths
    if not framework_src.is_dir():
        print(f"ERROR: gradle-testkit-framework not found at: {framework_src}", file=sys.stderr)
        return 1

    if not samples_dir.exists():
        print(f"ERROR: Samples directory not found: {samples_dir}", file=sys.stderr)
        return 1

    # Find all valid samples
    print(f"Scanning for samples in: {samples_dir}")
    samples = find_samples(samples_dir)

    if not samples:
        print("No valid samples found.")
        print("\nA valid sample must have:")
        print("  - original/build.gradle.kts")
        print("  - modified/build.gradle.kts")
        print("  - verification/*.java (at least one test file)")
        return 0

    print(f"Found {len(samples)} valid sample(s)\n")
    print("=" * 80)

    # Verify each sample in parallel
    results = []
    print_lock = threading.Lock()
    completed = [0]

    def verify_and_report(sample_dir: Path) -> Tuple[str, bool, str]:
        sample_name = sample_dir.name
        try:
            success, output = verify_sample(sample_dir, framework_src, verbose=False)
        except Exception as e:
            success, output = False, f"ERROR: {str(e)}"

        with print_lock:
            completed[0] += 1
            print(f"\n[{completed[0]}/{len(samples)}] Verifying: {sample_name}")
            print("-" * 80)

            if args.verbose or not success:
                print(output)
            else:
                # Show summary line only
                for line in output.strip().split('\n'):
                    if 'Verification:' in line:
                        print(line)
                        break

        return sample_name, success, output

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(verify_and_report, s) for s in samples]
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                print(f"ERROR: Verification failed with exception: {e}", file=sys.stderr)

    # Print summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)

    successful = sum(1 for _, success, _ in results if success)
    failed = len(results) - successful

    print(f"\nTotal samples: {len(results)}")
    print(f"Successful:    {successful} ✓")
    print(f"Failed:        {failed} ✗")
    print()

    for sample_name, success, _ in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}  {sample_name}")

    if failed > 0:
        print(f"\n{failed} sample(s) failed verification.")
        return 1

    print("\nAll samples passed verification!")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise
