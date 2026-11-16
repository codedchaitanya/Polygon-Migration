# Issue

## Ranking

One rule is used for both lists: silent damage to data first, then a cost paid on every problem,
then a cost that is visible or paid once.

| Rank | Issue | Severity | Why it is ranked here |
|------|-------|----------|-----------------------|
| P1 | Rate-limited fetch is treated as a success | High | The only one where the tool says "success" while data is missing |
| P2 | Tutorial and tags not carried over; update erases a stored editorial | Medium | Content is lost on every problem and the loss reaches the platform |
| P3 | Statement shown as raw HTML and unrendered math | Medium | Seen every time, but the stored data is correct |
| C1 | Failures in the main view are handled wrongly | High | Wrong behaviour exactly when something has already gone wrong |
| C2 | One view function does every job | Medium | Cause of repeated cost and risk, but no wrong result by itself |
| C3 | Migrations out of sync with the models | High | Loud, happens once, fixed by one command, and already fixed |

C3 has a higher severity than C2 but a lower rank. The reason is in its priority rationale.

## Summary

| Type | Critical | High | Medium | Low | Total |
|------|----------|------|--------|-----|-------|
| Product Issues | 0 | 1 | 2 | 0 | 3 |
| Code Issues | 0 | 2 | 1 | 0 | 3 |

---

## Product Issues

### [P1] A fetch that Polygon rate-limits is treated as a success, so incomplete test data can be migrated without warning

**Severity**: High

**Location**:
- `problems/polygon_api.py:399-402` (`get_all_test_cases`: on any error, log a warning and keep the test with empty input and output)
- `problems/views.py:259` and `:511` (the fetched list is cached in Redis for 30 minutes and reused by the migration steps)
- `problems/views.py:524` and `problems/polygon_api.py:742` (tests without input or output are skipped; the success message is shown regardless)

**Description**:
A fetch makes about two Polygon API calls per test case. When Polygon answers some of them with
HTTP 429 (Too Many Requests), the app does not report it.

Tested with problem 631620 (20 tests), fetching twice about 10 seconds apart:
- The first fetch returned all 20 tests.
- The second received 429 from test 14 onwards. The log shows seven "Error fetching test case" warnings.
- The page still loaded normally (HTTP 200, no error message) and still listed "20 total", with
  tests 14–20 having empty input and output.
- The incomplete list replaced the complete one in the Redis cache.

From reading the code (not tested, to avoid damaging the migrated data): the database and storage
steps read that cache, skip every test that has no input or output, and then show their normal
"successfully" message. The storage step also deletes the problem's existing files first, so a
complete earlier upload would be replaced by a partial one.

**Impact**:
- A problem can end up with fewer test cases in the database and in storage than it has on Polygon,
  while every step reported success. A judge using those files would accept wrong solutions.
- Nothing on the page states how many tests were fetched with content, saved or uploaded, so the user
  can only find out by counting rows in the table or files in the storage console.
- It is easy to trigger: fetching the same problem again within a minute was enough here. Problems with
  many more tests may hit the limit in a single fetch (likely, not tested).

**Suggested Fix**:
1. Retry a rate-limited call after a pause (honouring `Retry-After` when Polygon sends it), a few times.
2. If a test still cannot be downloaded, fail the fetch with a visible error that names the tests,
   and do not cache the incomplete result.
3. Block both migration steps when any test lacks input or output, instead of skipping it.
4. Put the counts in the result message, for example "15 of 15 test cases uploaded".

**Priority rationale**:
- Severity is High because it matches "significant data integrity risk" in the guidelines. It is not
  Critical: the source data on Polygon is intact, and a clean re-fetch and re-run repairs the problem.
- It is ranked first because it is the only product issue where the tool reports success while data
  is missing. The user has no way to notice without counting rows or files.
- The damage does not stay inside this tool. A problem with missing test cases makes the judge accept
  wrong solutions, so the people affected are the students, not the person migrating.
- It is easy to trigger: two fetches about ten seconds apart reproduced it.
- P2 and P3 cost the user time or content, but the user can see both. This one leaves wrong data
  that looks right.

---

### [P2] The tutorial and tags that already exist on Polygon are not carried over, and an update erases a stored editorial

**Severity**: Medium

**Location**:
- `problems/views.py:288-289` (`constraints = ''` and `editorial = ''` are set unconditionally)
- `problems/views.py:350-351` (on update, both empty values are written over the stored ones)
- `problems/polygon_api.py` (no call to `problem.viewTags`, and the tutorial is never requested)
- `problems/templates/problems/index.html` (tags field starts empty; no tutorial or editorial section is shown for a fetched problem)

**Description**:
Tested with problem 631790 (Two Sum), which on Polygon has the tags `hashing`, `implementation` and
`medium-easy`, and a written tutorial.

- After fetching, the page showed "No tags selected" and no difficulty. The tutorial did not appear anywhere.
- Tags had to be typed again by hand. Typing `hashing` and `arrays` created those two tags in the
  database; Polygon's `implementation` and `medium-easy` were not offered.
- After "Create/Update problem in Database", the row had `editorial = ''` although the model has an
  `editorial` field and Polygon had the text.

Tested separately against a throwaway test database with Polygon faked: a problem row that
already had an editorial and constraints was updated with "Create/Update problem in Database".
The page reported "updated in database successfully" and both fields were empty afterwards.

**Impact**:
- Every migrated problem needs its tags re-entered, and the result depends on what the user remembers
  and how they spell it, so tags drift away from Polygon's (here `arrays` instead of `implementation`).
- The tutorial is lost in migration with no warning; someone has to copy it over separately or it
  never reaches the platform.
- An editorial or constraints text added to the row later is erased by the next update, also with
  no warning.
- The tool's purpose is to copy a problem from Polygon; the migrated record is less complete than the source.

**Suggested Fix**:
1. Read the problem's tags with Polygon's `problem.viewTags` and pre-select them in the tags field,
   creating missing `ProblemTag` rows on save. Keep them editable.
2. Read the tutorial (it is part of `problem.statements` for each language), show it on the review
   page, and save it to `Problem.editorial`.
3. On update, never overwrite a stored editorial or constraints with an empty value.
4. Optionally suggest a difficulty when a tag such as `easy`, `medium-easy` or `hard` is present,
   leaving the final choice to the user.

**Priority rationale**:
- Severity is Medium as observed: nothing breaks, but the migrated record is less complete than the
  source ("feature partially broken"). It rises to High if editorials or constraints are ever
  written into these rows from anywhere else, because every update then erases them. That depends
  on how the platform uses the table and should be confirmed.
- It is ranked second because it happens on every problem, not only under a rate limit, and the loss
  reaches the platform: the editorial students would see stays empty.
- It is below P1 because the user can see the gap and repair it by hand, and nothing reports a false
  success about test data.
- It is above P3 because P3 stays on an internal review page and stores nothing wrong.
- When defending it, lead with the tutorial and the erased editorial. The brief asks for tags to be
  added by hand in the walkthrough, so manual tagging looks intended and the tags part is the weaker
  half.

---

### [P3] Fetched problem statement is shown as raw HTML and unrendered math

**Severity**: Medium

**Location**:
- `problems/templates/problems/index.html:203-234` (statement, input format, output format, notes)
- `problems/views.py:37-64` (`get_div_inner_html`, which returns each section as an HTML string)

**Description**:
After fetching a problem, the review page shows the statement with literal tags and math markers,
for example:

```
<p>You are given a grid with $$$n$$$ rows and $$$m$$$ columns. ...</p><ul> <li> $$$0$$$ — the cell is empty; </li>
```

Two separate causes:

1. `parse_problem_html` extracts each section from the package's `problem.html` as an HTML string.
   The template prints it as a normal variable, `{{ fetched_problem.problem_statement|linebreaksbr }}`.
   Django escapes variables by default, so `<p>` reaches the browser as `&lt;p&gt;` and is shown as text.
   `linebreaksbr` only converts newlines; it does not mark the value as HTML.
2. Polygon writes math as `$$$...$$$`, which Codeforces renders with MathJax. This page loads only
   Bootstrap's script, so the markers are never rendered.

Observed with problem 631620 (rotten-oranges); the same would happen for any problem, since it does not
depend on the statement's content.

**Impact**:
- "Review the data" is the step where the user checks the statement before clicking
  "Create/Update problem in Database". With tags and `$$$` markers mixed into the text, lists, paragraphs
  and formulas (constraints such as `1 ≤ n, m ≤ 100`) are hard to read, so mistakes in the statement are
  easy to miss before migrating.
- The user cannot tell whether what they see is a display problem or broken data that will be saved
  to the database in that form.

**Suggested Fix**:
1. Sanitize the four HTML fields on the server with an allowlist of formatting tags (`p`, `ul`, `ol`,
   `li`, `b`, `i`, `em`, `strong`, `code`, `pre`, `sub`, `sup`, `br`, `span`, table tags), for example
   with the `nh3` library, and only then mark the result as safe for the template. Drop `linebreaksbr`
   for these fields, since the HTML already carries its own structure.
2. Do not use `|safe` on the unsanitized value. The HTML comes from an external system, and marking it
   safe as-is would let any markup or script in a statement run in the staff user's session. Polygon
   generates this HTML from TeX, so the likelihood is low, but the app should not rely on that.
3. Load MathJax on the page and configure Polygon's delimiters: inline `$$$...$$$` and display
   `$$$$$$...$$$$$$`.
4. Leave the stored values unchanged. This is a display fix; whether the database should hold raw or
   sanitized HTML depends on how the platform that reads these rows renders them, which should be
   confirmed first.

**Priority rationale**:
- Severity is Medium because it is "poor UX" on the review step, which is the only check the user
  has before saving. It is not Low or cosmetic for that reason, and not High because no data is lost
  or stored wrongly.
- It is ranked third because it is the most visible issue but the least harmful: it affects an
  internal page, the stored statement is correct, and the fix is small.
- It affects every problem and every user, so it should still be fixed early. Rank here reflects
  harm, not effort; as a quick win it could be done first.
- This is the closest call in the product list. If you would rather argue that an unreadable review
  step lets statement mistakes through on every migration, swapping P2 and P3 is defensible.

---

## Code Issues

### [C1] Failures in the main view are handled wrongly: the error handler calls a method that does not exist and reports a rollback that did not happen

**Severity**: High

**Location**:
- `problems/views.py:186-187` (one `try` and one `transaction.atomic()` wrapped around every action)
- `problems/views.py:216-226` (the storage step runs inside that database transaction; its cleanup is
  a commented-out line marked "pseudo-code, implement as needed")
- `problems/views.py:336` and `:502` (missing user input is reported with `raise Exception(...)`)
- `problems/views.py:553-560` (the single handler: fixed message, `api.delete_azure_blob(...)`, cache clear)
- `problems/polygon_api.py` (`PolygonAPI` has no `delete_azure_blob` method)

**Description**:
Everything the view does after reading the form sits in one `try` block with one `except Exception`.
That handler treats a missing form field, a Polygon error and a storage error the same way: it shows
"Migration failed and all changes have been rolled back", calls a cleanup method, and clears the
problem's cached test cases.

Tested by calling the real view against a throwaway test database, with Polygon, Redis and storage
replaced by fakes (no real service was touched):

1. Storage upload succeeds, then a later Polygon call in the same request fails. After uploading,
   the view goes on to fetch the problem info and package again for display. When that fetch failed,
   the handler ran `api.delete_azure_blob(...)` and the request ended with an unhandled
   `AttributeError: 'PolygonAPI' object has no attribute 'delete_azure_blob'`, a 500 page. Storage
   had gone from 10 old files to 6 new ones, so the upload had in fact completed.
2. The upload itself fails half way (third file). The page showed "Migration failed and all changes
   have been rolled back. Reason: simulated upload failure". Storage held only `01` and `01.a`: the
   10 files that were there before the request had been deleted and were not restored.
3. "Create/Update problem in Database" with no difficulty selected. The page showed "Migration failed
   and all changes have been rolled back. Reason: Please select a difficulty level before migrating
   to database.", and the cached test cases were cleared, although nothing had been attempted.

Note on case 2: in the starter code the old Azure class caught and logged every upload and delete
error, so this case reported success instead. The storage change in this repository raises the error,
which is how it now reaches this handler. Cases 1 and 3 are the same in the starter code.

**Impact**:
- The one path written to clean up after a failed migration can never work, and nothing has caught
  it: it only runs when something else has already gone wrong, and there are no tests.
- "All changes have been rolled back" is only true for the database. A database transaction cannot
  undo deleted or uploaded files, so storage can be left empty or partial while the page says
  otherwise.
- A user who forgets a field is told a migration failed, and pays for it with a full re-fetch from
  Polygon on the next click because the cache was cleared.
- With a single catch-all, the log and the page cannot distinguish a user mistake, a Polygon outage
  and a storage outage.

**Suggested Fix**:
1. Check the form input before any work starts and return a normal validation message. Do not raise
   exceptions for it and do not clear the cache.
2. Take the storage step out of the database transaction; keep the transaction around database
   writes only.
3. Make the storage step safe to fail: upload the new files first, then delete the old ones that are
   no longer needed, so a failure half way leaves the previous set usable. Remove the call to the
   method that does not exist.
4. Catch specific errors (Polygon, storage, database) separately and say exactly what state each
   one leaves behind, instead of one fixed sentence.
5. Add a test for each failure path, with Polygon and storage faked.

**Priority rationale**:
- Severity is High: the clean-up path cannot run at all ("major functionality broken"), and storage
  can be left partial while the page says everything was rolled back ("significant data integrity
  risk"). It is not Critical because it needs another failure to happen first.
- It is ranked first because the code is wrong exactly when something has already gone wrong, which
  is when the user most needs the page to be accurate.
- The triggers are realistic. Polygon rate limits were easy to hit in this project, and any Polygon
  error after a successful upload is enough.
- It is ahead of C2 because it is a small, contained fix to a path that can lose files today.
  Restructuring is a larger change and should not be built on top of a broken failure path.

---

### [C2] One view function does every job, so each button repeats the whole Polygon fetch and the same code is copied in several places

**Severity**: Medium

**Location**:
- `problems/views.py:88-569` (`index`: one function of about 480 lines behind one URL; the action is
  chosen by which hidden form field is present, lines 126-128)
- `problems/views.py:234-308` (problem info, package download, checker and test list, run on every
  POST whatever the action)
- `problems/views.py:160` (`problem.updateWorkingCopy`, a call that changes state on Polygon, made
  on every POST for a problem that is already in the database)
- Copied blocks: main-solution lookup at `views.py:156-184` and `:469-495`; "read cache or fetch"
  at `views.py:248-254`, `:426-434`, `:505-513` and `polygon_api.py:719-727`; checker compile and
  upload at `polygon_api.py:601-646` and `:647-691`; Redis client set-up at `polygon_api.py:772-778`,
  `:801-807`, `:848-854`, `:900-906`
- `problems/tests.py` (empty)

**Description**:
Fetching, saving the problem, saving test cases and uploading to storage are four actions for the
user, but in the code they are branches of one function. Whatever button is pressed, the function
first runs the code for a problem that already exists, then the storage branch if requested, then
the full "fetch for display" block, then the database branches. HTTP handling, Polygon calls,
parsing, database writes, storage and the data for the template are all mixed in the same body, and
`PolygonAPI` also holds the Redis cache and the checker compilation.

Tested by counting the HTTP calls the view makes to Polygon for each button, with Polygon faked, for
a problem that is already in the database and whose 3 test cases are already cached:

| Button | Polygon calls |
|---|---|
| Fetch | 17 (11, plus 2 per test case) |
| Create/Update problem in Database | 12 |
| Migrate Test Description to Database | 10 |
| Migrate Test Cases to Azure | 12 |

"Migrate Test Description to Database" only needs the cached test cases, yet it asked Polygon for
the problem info twice, the package list, the package download, the checker twice, the test list,
the solutions and the solution source, and updated the working copy. The storage button asked for
the checker four times.

**Impact**:
- Each step is slower than it needs to be and depends on Polygon being available, even when all the
  data it needs is already cached.
- More calls per click means the rate limit is reached sooner, and a failed display fetch can fail a
  step whose own work had succeeded.
- A fix has to be made in every copy: the cache-or-fetch block exists four times and the
  main-solution block twice.
- The function cannot be tested in parts, and there are no tests, so a change to one action can
  break another without anyone noticing.
- Viewing a problem has a side effect on Polygon (`updateWorkingCopy`) that the user did not ask for.

**Suggested Fix**:
1. Split the work into small functions with one job each: fetch a problem snapshot from Polygon
   (statement, limits, checker, tests), save the problem, save the test cases, upload the test cases.
2. Give each action its own view (or URL) that reads the cached snapshot, does only its own work,
   and then redirects back to the page.
3. Cache the whole snapshot once per fetch, not only the test cases, so later steps need no Polygon
   calls.
4. Put the cache access in one helper with one Redis client (or use Django's cache framework, which
   `views.py:9` already imports but never uses), and keep one copy of each duplicated block.
5. Add unit tests for each function with Polygon faked.

**Priority rationale**:
- Severity is Medium because the guidelines place code maintainability and code duplication there,
  and the function produces no wrong result by itself.
- It is ranked second because it is the cause behind several other costs: 10 to 12 Polygon calls per
  button where none were needed, a higher chance of reaching the rate limit in P1, and no way to
  test one action without the others.
- It is the most direct match for how the brief describes code issues: how the backend is structured
  and organized.
- It is below C1 because the dangerous path gets fixed before the restructuring starts, and because
  restructuring is the largest change here with no tests to protect it.
- It is separate from C1: splitting the function would not make the failure handler correct, and
  correcting the handler does not need the split.

---

### [C3] Database migrations are out of sync with the models, so a fresh setup crashes on the first fetch

**Severity**: High

**Location**:
- `problems/models.py:79-80` (`Problem.notes`, `Problem.genie_chat`)
- `problems/migrations/0001_initial.py` (creates neither column)
- First failure: `problems/views.py:146`, `Problem.objects.filter(polygon_id=polygon_id).first()`

**Description**:
The `Problem` model defines `notes` and `genie_chat`, but the only migration shipped for the app,
`0001_initial.py`, does not create those columns. After following the README (`python manage.py migrate`),
the first "Fetch" on any problem ID returned a 500 error page:

```
ProgrammingError: column problems_problem.notes does not exist
```

`python manage.py makemigrations --dry-run` on the untouched starter code confirmed the gap: it proposed
`0002_problem_genie_chat_problem_notes.py` with "Add field genie_chat to problem" and "Add field notes to problem".
(Tested behaviour, not a conclusion from reading code.)

**Impact**:
- A new engineer who follows the setup instructions exactly gets an application where fetching, and
  therefore every migration step after it, is unusable.
- The error names a missing column, not a missing migration, so the cause is not obvious to someone
  new to the codebase.
- It shows that model changes can be committed without their migration and nothing catches it: the
  three `tests.py` files are empty placeholders and the repository has no CI configuration.

**Suggested Fix**:
1. Commit the missing migration (already done in this repository: `0002_problem_genie_chat_problem_notes.py`).
2. Prevent a repeat: run `python manage.py makemigrations --check --dry-run` in CI or a pre-commit hook,
   so a model change without a migration fails before it is merged.
3. Add one smoke test that loads the index view against a migrated test database; it would have failed
   on this bug.

**Priority rationale**:
- Severity is High because on a fresh database the entry point of every flow fails ("major
  functionality broken"). It is not Critical: no data is lost and there is no security impact.
- It is ranked third although its severity is higher than C2's. Severity is how bad it is when it
  happens; priority also counts how often it happens, how visible it is, and what it leaves behind.
- This one happens once per new environment, fails in the first minute with an error that names the
  missing column, is fixed by one command, and cannot corrupt data. It is already fixed in this
  repository.
- What remains is that nothing checks for a model change without its migration. That part is small:
  one `makemigrations --check` step in CI or a pre-commit hook.
- If you want rank to follow severity strictly, swap C2 and C3 and say that a setup blocker comes
  before maintainability.

---

## Edge Case Analysis

How these were checked: each case was run through the real view code against a throwaway test
database, with Polygon, the Redis cache and storage replaced by fakes that return the data described
in the question. "Tested" below means that. It was not done in the browser against the real Polygon
and Azure, so that the two migrated problems were not disturbed. Points marked "from reading the
code" were not run. Rewrite the answers in your own words, and reproduce at least Q1 and Q3 in the
real app before you rely on them; both are safe to try.

### Q1

> A Polygon problem has 0 sample test cases but 15 regular test cases. What happens when you migrate this problem?

The migration completes and every step reports success, but the problem ends up with no examples.

Tested:
- "Create/Update problem in Database" created the problem with `test_case_count = 15` and no
  `SampleTestCase` rows. The code filters the tests where `is_sample` is true
  (`problems/views.py:439`), gets an empty list, and the loop does nothing.
- "Migrate Test Description to Database" created 15 `ProblemTestCase` rows, all with `is_sample = False`.
- "Migrate Test Cases to Azure" uploaded 30 files, `01` to `15` and `01.a` to `15.a`.
- No step showed a warning or an error.

Why it matters: the judge has all its test files, so submissions can be evaluated. A student opening
the problem would see a statement with no example input and output, and nothing told the person
migrating that this was the case. The fix is a warning (or a block) when a problem has no sample.

### Q2

> A problem is migrated with 20 test cases. Later, the problem setter removes 8 test cases on Polygon (now 12 remain). The problem is re-migrated. What happens?

Storage ends up correct, the database does not, and every step reports success.

Tested, with 20 tests of which 3 were samples, then test 3 (a sample) and tests 14 to 20 removed:
- Storage: correct. The storage step deletes all of the problem's files and then uploads, so it went
  from 40 files to 24 (`01` to `12` and their `.a` files).
- `Problem.test_case_count`: became 12, but only because "Create/Update problem in Database" was
  pressed again. That step is the only one that sets it.
- `ProblemTestCase`: still 20 rows. The code updates existing rows by position and creates extra
  ones when needed, but never deletes (`problems/views.py:516-549`). Rows 1 to 12 were overwritten
  with the 12 current tests; rows 13 to 20 kept the old content of old tests 13 to 20. Old test 13
  therefore appeared twice (rows 12 and 13), and tests that no longer exist on Polygon were still
  in the table.
- `SampleTestCase`: still 3 rows. The same update-by-position logic (`problems/views.py:441-463`)
  left the third row holding the removed sample, so a deleted example would still be shown.

Also tested: if a migrate button is pressed without fetching again while the earlier fetch is still
cached (30 minutes), the cached list of 20 is used and nothing changes, again with a success message.

Why it matters: the three places that describe the same problem now disagree: 12 in storage, 12 in
`test_case_count`, 20 test rows and one stale sample in the database. Anything that reads the test
rows or samples from the database shows data that no longer exists on Polygon. The fix is to make
the saved rows match the fetched list: delete the rows beyond the new count, or delete and recreate
them all inside the transaction.

### Q3

> Two different Polygon problems have the exact same title: "Two Sum". You migrate the first one successfully. Then you try to migrate the second one. What happens?

The second problem cannot be migrated. The first one is not affected.

Tested:
- Fetching the second problem works and shows its data.
- "Create/Update problem in Database" fails. The view looks the problem up by `polygon_id`, does not
  find it, and tries to create it with `slug = slugify(title)`, which is `two-sum` again
  (`problems/views.py:284`, `:340`, `:368`). `Problem.slug` is unique, so the database rejects it.
  The page showed: "Migration failed and all changes have been rolled back. Reason: duplicate key
  value violates unique constraint "problems_problem_slug_key" DETAIL: Key (slug)=(two-sum) already
  exists."
- No `Problem` row was created for the second problem, its cached test cases were cleared, and the
  first problem's row, samples, test rows and storage files were unchanged.
- The two test-case steps then refused with "Please migrate the problem to the database first".
  In the browser those two buttons stay disabled (from reading the code in the template, not run).

Why it matters: the user gets a raw database error instead of an explanation, and the page offers no
way forward, because neither the title nor the slug can be edited there. The only workaround is to
rename the problem on Polygon and build a new package. Titles are not unique on Polygon, so this
will happen with common names. The fix is to detect the clash before saving and either let the user
edit the slug or make it unique automatically (for example by adding the Polygon ID), with a clear
message.

### Q4

> When test cases are saved to the database via "Migrate Test Cases to DB", some data is intentionally discarded. What data is lost? Why might this cause problems?

What is discarded (the button is labelled "Migrate Test Description to Database" in the page):

1. Everything after the first 260 characters of each test's input and of its output
   (`problems/views.py:525-527`). The code comment says "260 bytes"; it cuts characters.
2. Trailing whitespace and blank lines at the end of input and output, removed with `rstrip()`
   before the cut (`problems/views.py:519-520`).
3. Any test whose input or output is empty: it is skipped and gets no row (`problems/views.py:524`).
4. Polygon's own test number. The row stores `order`, which counts saved rows only. The `manual`
   flag is not stored either.

Tested with six tests, where test 2 was 1000 characters long, tests 3 and 4 differed only after
character 300, and test 5 had an empty answer:
- Test 2 was stored as 260 characters of input and 260 of output. The full 1000 were in storage.
- Tests 3 and 4 were stored with identical input, so the rows cannot be told apart.
- Test 1's trailing blank lines were gone in the row but present in the storage file.
- Five rows were saved for six tests, numbered 1 to 5 with no gap. Storage had files `01` to `04`
  and `06`, with no `05`, because the storage step numbers by position. Row 5 in the database is
  therefore file `06` in storage. `test_case_count` was 6.
- The sample rows (`SampleTestCase`, written by the create step) are not cut: the sample kept its
  full length there.

Why this might cause problems:
- The rows are previews, not test data, but nothing in the table says so. There is no flag for
  "truncated" and no stored full length, so anyone who judges, displays or exports from these rows
  uses incomplete inputs and outputs without knowing.
- Different tests can become identical rows, which makes the table useless for telling which test a
  submission failed on.
- When a test is skipped, row numbers and storage file numbers stop matching, so a row can point a
  reader at the wrong file.
- The count on the problem, the number of rows and the number of files can all differ, with a
  success message each time.

A reasonable fix keeps the preview but makes it honest: store the Polygon test number and a
"truncated" flag (or the full length) on each row, number rows and files the same way, and report
skipped tests instead of dropping them silently.

---


