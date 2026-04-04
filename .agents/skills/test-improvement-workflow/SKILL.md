---
name: test-improvement-workflow
description: This skill should be used when the user asks to "improve test quality", "refactor tests", "audit tests and fix them", or wants a systematic workflow for improving test suite quality using Dave Farley's principles. Orchestrates the test-design-reviewer, tdd, and refactoring skills into a complete improvement workflow.
---

# Test Improvement Workflow

A systematic workflow for improving test suite quality using Dave Farley's 8 properties of good tests. This skill orchestrates the `test-design-reviewer`, `tdd`, and `refactoring` skills into a complete improvement cycle.

## Prerequisites

Ensure these skills are available in the workspace:
- `test-design-reviewer` - For auditing test quality using Dave Farley's framework
- `tdd` - For RED-GREEN-MUTATE-KILL MUTANTS-REFACTOR cycle
- `refactoring` - For safe, behavior-preserving code improvements

## Workflow Overview

```
┌─────────────────────────────────────────────────────────────┐
│  1. AUDIT: Run test-design-reviewer to get Farley Score     │
├─────────────────────────────────────────────────────────────┤
│  2. PRIORITIZE: Ask for most efficient order of fixes       │
├─────────────────────────────────────────────────────────────┤
│  3. PLAN: Create task list with skill assignments           │
│     • TDD skill for new code (RED → GREEN)                  │
│     • Refactoring skill for existing code changes           │
├─────────────────────────────────────────────────────────────┤
│  4. EXECUTE: Follow plan, commit after each phase           │
├─────────────────────────────────────────────────────────────┤
│  5. VERIFY: Run unbiased re-audit in NEW conversation       │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 1: Initial Audit

Run the test-design-reviewer skill to evaluate current test quality:

```
test-design-reviewer audit test quality of each test file and make a report of results
```

This produces:
- Property scores (Understandable, Maintainable, Repeatable, Atomic, Necessary, Granular, Fast, First)
- Farley Score (1-10 weighted average)
- Top recommendations for improvement

---

## Step 2: Prioritize Recommendations

After receiving recommendations, ask the test-design-reviewer for the most efficient implementation order:

```
test-design-reviewer suggest an order for the top 3 recommendations that is most efficient
```

The response should consider:
- **Dependencies** between recommendations
- **Foundation-first** approach (fix patterns before consolidating)
- **Effort vs impact** tradeoffs

### Example Priority Order

| Order | Recommendation | Rationale |
|-------|----------------|-----------|
| 1st | Reduce implementation coupling | Design decision affecting future code |
| 2nd | Consolidate with parameterization | Uses cleaner patterns from step 1 |
| 3rd | Extract common helpers | Fewer places to apply after consolidation |

---

## Step 3: Create Implementation Plan

Create a detailed task plan with skill assignments:

```
create a plan for this order
```

### Skill Assignment Rules

| Task Type | Skill | When to Use |
|-----------|-------|-------------|
| Adding new code | **TDD** | New helper methods, new test utilities |
| Modifying existing code | **Refactoring** | Consolidating tests, updating assertions |
| Verification | **TDD** | Running tests, checking coverage |

### Plan Structure

Each phase should follow this pattern:

**For new functionality (TDD skill):**
1. 🔴 **RED**: Write failing tests for new behavior
2. 🟢 **GREEN**: Implement minimum code to pass
3. ✅ **VERIFY**: Run tests to confirm GREEN
4. 💾 **COMMIT**: Save working code before refactoring

**For code improvements (Refactoring skill):**
1. 💾 **COMMIT FIRST**: Always commit working code before refactoring
2. 🔄 **REFACTOR**: Make behavior-preserving changes
3. ✅ **VERIFY**: Run tests to confirm no regressions
4. 💾 **COMMIT**: Save refactored code

### Example Plan Structure

```markdown
## Phase 1: Reduce Implementation Coupling [TDD skill]

### 1.1 RED: Write failing tests for is_unchanged() helper
[TDD skill] Write tests expecting is_unchanged(key) method before implementing

### 1.2 GREEN: Implement is_unchanged() helper
[TDD skill] Write minimum code to make tests pass

### 1.3 COMMIT before refactoring
[TDD skill] Save working code as safety net

### 1.4 REFACTOR: Update existing tests to use helper
[Refactoring skill] Replace old assertions with new helper. No behavior change.

### 1.5 VERIFY and COMMIT
[TDD skill] Run all tests, then commit refactoring
```

---

## Step 4: Execute the Plan

Follow the plan systematically:

### TDD Cycle (for new code)

```bash
# 1. Write failing test
# 2. Run test - confirm it fails (RED)
pytest test_file.py::TestClass::test_method -v

# 3. Implement minimum code
# 4. Run test - confirm it passes (GREEN)
pytest test_file.py::TestClass::test_method -v

# 5. Commit before refactoring
git add -A && git commit -m "feat: add helper method"
```

### Refactoring Cycle (for existing code)

```bash
# 1. Commit current working state FIRST
git add -A && git commit -m "checkpoint: before refactoring"

# 2. Make refactoring changes
# 3. Run ALL tests to verify no regressions
pytest test_file.py -v

# 4. Commit refactoring
git add -A && git commit -m "refactor: consolidate tests with parameterization"
```

### Commit Message Conventions

| Type | Format | Example |
|------|--------|---------|
| New feature | `feat: <description>` | `feat: add is_unchanged() helper to UpdateResult` |
| Refactoring | `refactor: <description>` | `refactor: consolidate tests with @pytest.mark.parametrize` |
| Tests only | `test: <description>` | `test: add failing tests for new helper` |

---

## Step 5: Unbiased Final Audit

**Critical**: Run the final audit in a **new conversation** to ensure unbiased evaluation.

### Why a New Conversation?

- No prior knowledge of target scores
- No context bias from implementation work
- Objective assessment of current code state only

### Instructions for Final Audit

Start a new OpenHands conversation with:

```
test-design-reviewer audit test quality of each test file and make a report of results
```

**Important**: Do NOT include any target scores or expectations in the prompt.

### Comparing Results

After receiving the new audit:
1. Compare Farley Scores (before vs after)
2. Review individual property improvements
3. Document any remaining recommendations for future work

---

## Common Improvement Patterns

### Pattern 1: Reduce Implementation Coupling

**Problem**: Tests directly access internal data structures

```python
# Before (coupled to internal structure)
assert ("key", "value") in result.unchanged
```

**Solution**: Add helper methods to production code

```python
# After (uses abstraction)
assert result.is_unchanged("key")
```

### Pattern 2: Consolidate with Parameterization

**Problem**: Multiple similar test methods

```python
# Before (redundant)
def test_case_a(self):
    assert func("a") == "A"

def test_case_b(self):
    assert func("b") == "B"
```

**Solution**: Use `@pytest.mark.parametrize`

```python
# After (consolidated)
@pytest.mark.parametrize("input,expected", [
    ("a", "A"),
    ("b", "B"),
])
def test_func_transforms_correctly(self, input, expected):
    assert func(input) == expected
```

### Pattern 3: Extract Common Assertions

**Problem**: Repeated assertion patterns across tests

```python
# Before (duplicated)
content = file.read_text()
assert "key1" in content
assert "key2" in content
```

**Solution**: Create reusable helper in conftest.py

```python
# conftest.py
def assert_file_contains_all(file_path, expected_strings):
    content = file_path.read_text()
    for expected in expected_strings:
        assert expected in content

# Test file
assert_file_contains_all(file, ["key1", "key2"])
```

---

## Workflow Summary

| Step | Action | Skill |
|------|--------|-------|
| 1 | Audit test quality | test-design-reviewer |
| 2 | Prioritize recommendations | test-design-reviewer |
| 3 | Create implementation plan | TDD + Refactoring |
| 4 | Execute plan with commits | TDD + Refactoring |
| 5 | Re-audit in new conversation | test-design-reviewer |

---

## Quick Start

To begin the test improvement workflow:

1. **Audit**: `test-design-reviewer audit test quality of each test file and make a report of results`

2. **Prioritize**: `test-design-reviewer suggest an order for the top 3 recommendations that is most efficient`

3. **Plan**: `create a plan for this order that uses the refactoring skill where refactor is mentioned and the tdd skill elsewhere`

4. **Execute**: Follow the plan, committing after each phase

5. **Re-audit**: Start a NEW conversation with: `test-design-reviewer audit test quality of each test file and make a report of results`
