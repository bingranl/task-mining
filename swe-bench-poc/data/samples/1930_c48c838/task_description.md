# Task Description

**PR**: https://github.com/android/nowinandroid/pull/1930

## Bad Commit
- SHA: c48c8381e1d97eccfdcd367759c8af5d5cdaa4d6
- Message: Upgradle to 9.0.0

## Good Commit
- SHA: 7ff1913855ad1db355875502e964d7e12947241b
- Message: Fixes host test tasks that were accidentally attemping to run

## Files Changed
- app/build.gradle.kts
- build-logic/convention/src/main/kotlin/com/google/samples/apps/nowinandroid/AndroidCompose.kt
- core/data/build.gradle.kts
- core/designsystem/build.gradle.kts
- core/network/build.gradle.kts
- feature/foryou/build.gradle.kts

## Category
Dependency Update

## Objective
Fix the build script issue identified in the bad commit.
