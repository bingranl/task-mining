# Task Description

## Problem
The original `build.gradle.kts` uses JUnit 4 for tests.

## Solution
Update the build script to use JUnit 5 (`org.junit.jupiter:junit-jupiter:5.10.0`).

## Verification Strategy
Run `GradleRunner` and assert that `testRuntimeClasspath` contains `org.junit.jupiter:junit-jupiter:5.10.0`.
