# Task Description

## Problem
The original build script is missing a `generateDocs` task.

## Solution
Add a `generateDocs` task.

## Verification Strategy
Run `tasks --all` via `GradleRunner` and assert that `generateDocs` appears in the output.
