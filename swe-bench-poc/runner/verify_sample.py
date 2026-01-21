#!/usr/bin/env python3

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _require_file(path: Path, description: str) -> None:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Missing {description}: {path}")


def _require_dir(path: Path, description: str) -> None:
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"Missing {description}: {path}")


def _run_tests(framework_dir: Path, sample_name: str, variant_label: str, build_file: Path, test_classes: list[str]) -> tuple[bool, str]:
    gradle_cmd = framework_dir / "gradlew"
    env = os.environ.copy()
    cmd = (
            [str(gradle_cmd)]
            + [
                "--no-daemon",
                "test",
                f"-Dsample.name={sample_name}",
                f"-Dsample.variant={variant_label}",
                f"-Dsample.buildFile={str(build_file)}",
            ]
            + [f"--tests={test_class}" for test_class in test_classes]
    )

    proc = subprocess.run(
        cmd,
        cwd=str(framework_dir),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc.returncode == 0, proc.stdout


def verify_sample(sample_dir: Path, framework_src: Path, verbose: bool = True) -> tuple[bool, str]:
    """
    Core verification logic for a single sample.
    
    Args:
        sample_dir: Path to the sample directory
        framework_src: Path to the gradle-testkit-framework directory
        verbose: Whether to print progress messages
    
    Returns:
        Tuple of (success: bool, output: str)
    """
    output_lines = []
    
    def log(msg: str = "") -> None:
        """Helper to capture output."""
        if verbose:
            print(msg)
        output_lines.append(msg)
    
    try:
        _require_dir(sample_dir, "sample directory")
        sample_name = sample_dir.name
        _require_dir(framework_src, "gradle-testkit-framework")

        original_build = sample_dir / "original" / "build.gradle.kts"
        modified_build = sample_dir / "modified" / "build.gradle.kts"
        verification_dir = sample_dir / "verification"
        _require_file(original_build, "original build.gradle.kts")
        _require_file(modified_build, "modified build.gradle.kts")
        _require_dir(verification_dir, "verification directory")

        test_files = sorted([p for p in verification_dir.glob("*.java") if p.is_file()])
        if not test_files:
            raise FileNotFoundError(f"No .java tests found in: {verification_dir}")

        log(f"Sample: {sample_name}")
        log(f"Framework: {framework_src}")
        log()

        with tempfile.TemporaryDirectory(prefix="swe_bench_poc_verify_") as tmp:
            tmp_dir = Path(tmp)
            framework_dir = tmp_dir / "framework"
            shutil.copytree(framework_src, framework_dir)

            dest_tests_dir = framework_dir / "src" / "test" / "java"
            dest_tests_dir.mkdir(parents=True, exist_ok=True)

            log("Copying verification test(s)...")
            test_classes = []
            for test_file in test_files:
                dest_name = test_file.name
                class_name = None
                try:
                    content = test_file.read_text(encoding="utf-8")
                    m = re.search(r"\bpublic\s+class\s+([A-Za-z_][A-Za-z0-9_]*)\b", content)
                    if m:
                        class_name = m.group(1)
                        expected_name = f"{class_name}.java"
                        if dest_name != expected_name:
                            dest_name = expected_name
                except Exception:
                    # Best-effort; if we can't parse, keep the original filename.
                    pass

                shutil.copy2(test_file, dest_tests_dir / dest_name)
                if dest_name == test_file.name:
                    log(f"  Copied test: {test_file.name}")
                else:
                    log(f"  Copied test: {test_file.name} -> {dest_name}")
                
                # Collect class name for targeted test execution
                if class_name:
                    test_classes.append(class_name)
                else:
                    # Fallback: derive class name from filename
                    test_classes.append(dest_name.replace(".java", ""))
            log()

            log("Testing with Original (O) build script...")
            log("=" * 60)
            ok_original, out_original = _run_tests(framework_dir, sample_name, "O", original_build, test_classes)
            if ok_original:
                log("Original PASSED (unexpected)")
            else:
                log("Original FAILED (as expected)")

            log()
            log("Testing with Modified (M) build script...")
            log("=" * 60)
            ok_modified, out_modified = _run_tests(framework_dir, sample_name, "M", modified_build, test_classes)
            if ok_modified:
                log("Modified PASSED (as expected)")
            else:
                log("Modified FAILED (unexpected)")

            log()
            log("=" * 60)
            log("VERIFICATION RESULT")
            log("=" * 60)
            log(f"Original (O): {'PASS ✗' if ok_original else 'FAIL ✓'}")
            log(f"Modified (M): {'PASS ✓' if ok_modified else 'FAIL ✗'}")

            success = (not ok_original) and ok_modified
            log()
            log(f"Verification: {'SUCCESS' if success else 'FAILED'}")

            if not success:
                log("\n--- Captured output (Original) ---\n")
                log(out_original)
                log("\n--- Captured output (Modified) ---\n")
                log(out_modified)

            return success, "\n".join(output_lines)
    
    except Exception as e:
        error_msg = f"ERROR: {e}"
        log(error_msg)
        return False, "\n".join(output_lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a sample by running its verification tests against original and modified build scripts."
    )
    parser.add_argument("sample_dir", type=str, help="Path to a sample directory")
    args = parser.parse_args()

    sample_dir = Path(args.sample_dir).resolve()
    framework_src = (Path(__file__).resolve().parent.parent / "gradle-testkit-framework").resolve()
    
    success, _ = verify_sample(sample_dir, framework_src, verbose=True)
    return 0 if success else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        raise
