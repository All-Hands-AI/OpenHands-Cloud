# Helm Chart Publishing Race Condition

## Summary

A race condition exists in the Helm chart publishing workflow that can leave the `main` branch in a broken state when multiple PRs modify the same chart concurrently.

## Root Cause Analysis

The race condition occurs when two PRs that modify the same chart are merged in quick succession:

### Timeline Example (PR #531 Incident)

1. **Initial State**: `main` branch has `openhands` chart at version `0.4.0`

2. **PR #531 Opens**: 
   - Based on commit `1833cd3dc8474d7aa203ba410ce29bafbad1a237` (openhands: `0.4.0`)
   - Bumps `openhands` from `0.4.0` → `0.4.1`
   - PR validation passes ✅ (compares against `origin/main` which has `0.4.0`)

3. **PR #473 Merges First**:
   - Also bumped `openhands` from `0.4.0` → `0.4.1`  
   - Now `main` has `openhands` at `0.4.1`

4. **PR #531 Merges**:
   - Still contains `openhands: 0.4.1`
   - GitHub merge succeeds (no conflict on version field since both target `0.4.1`)
   - Merge commit `0de14f6dc4807f9310626a9beeba0d7e0610a0d0`

5. **Post-merge Validation Fails**:
   - `publish-helm-charts.yml` compares `HEAD` vs `HEAD~1`
   - `HEAD` (merge commit): `openhands: 0.4.1`
   - `HEAD~1` (previous main): `openhands: 0.4.1`
   - **No version bump detected** → validation fails
   - `automation:0.1.2` is not published (sequential publishing stops)

### The Gap in Validation

| Stage | Comparison | PR #531 Result |
|-------|------------|----------------|
| PR Check | `HEAD` vs `origin/main` (at PR open time) | `0.4.1` vs `0.4.0` ✅ |
| Post-merge | `HEAD` vs `HEAD~1` (commit before merge) | `0.4.1` vs `0.4.1` ❌ |

The PR validation passes because it compares against the base branch **at the time the PR was created**, not the **current** state of main at merge time.

## Solutions

### ✅ Recommended: Require Branch to Be Up-to-Date Before Merging

Enable GitHub Branch Protection setting: **"Require branches to be up to date before merging"**

**How it works:**
1. PR #531 would be blocked from merging after PR #473 merged
2. Author must update/rebase PR #531 against latest `main`
3. After rebase, PR validation runs again against updated `origin/main` (now `0.4.1`)
4. Validation would fail because `0.4.1` → `0.4.1` is not a version bump
5. Author must bump to `0.4.2` to pass validation

**Configuration (Repository Settings → Branches → main):**
- ✅ Require status checks to pass before merging
- ✅ Require branches to be up to date before merging
- ✅ Require `validate-chart-versions / validate-chart-versions` as status check

**Pros:**
- Prevents the race condition entirely
- Uses existing GitHub infrastructure
- Forces PRs to always validate against latest main

**Cons:**
- Adds friction (must update branch before merge)
- May require more frequent rebasing

### Alternative: Use Merge Queue

GitHub Merge Queue serializes PRs, automatically rebasing each before merge.

**Pros:**
- Fully automated
- Handles rebasing automatically

**Cons:**
- Requires GitHub Enterprise or Teams plan
- More complex setup

### Complementary: Enforce Version Bump on PRs

Change `preview-helm-charts.yml` to set `enforce_version_bump: true`:

```yaml
validate-chart-versions:
  uses: ./.github/workflows/validate-chart-versions.yml
  with:
    base_ref: origin/${{ github.event.pull_request.base.ref }}
    enforce_version_bump: true  # Changed from false
```

**Important:** This alone does NOT prevent the race condition. It only converts warnings to errors. Combined with "require up-to-date branches", it ensures:
1. PR must be rebased before merge
2. After rebase, version validation enforces a bump against current main

## Recovery from Broken State

If a race condition has already occurred and publishing failed:

### Option A: Bump Chart Version in New PR

```bash
# Bump the version of any chart that failed to publish
yq -i '.version = "X.Y.Z"' charts/<chart-name>/Chart.yaml
```

### Option B: Re-run Publish Workflow

If the chart version is already higher than what's in GHCR:
1. Go to Actions → Publish Helm Charts
2. Click "Run workflow" → Select `main` branch → Run

## Related Issues and PRs

- Issue #545: This documentation
- PR #531: Original PR that triggered the race condition
- PR #473: The PR that merged first, also bumping to `0.4.1`
- PR #543: Downstream PR affected by unpublished `automation:0.1.2`

## References

- [GitHub: Require branches to be up to date](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-status-checks-before-merging)
- [GitHub: Merge Queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)
