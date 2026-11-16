# Polygon Migration Tool — Functionality Documentation

How to read it:
- Paths are relative to `PolygonMigration/`. Line numbers refer to the `azure-storage-interface`
  branch.
- Flows 1.1 to 1.5 were all run in the browser with problems 631620 (Rotten Oranges) and 631790
  (Two Sum). The custom-checker part of flow 1.5 was not exercised, because both problems use the
  standard checker `std::ncmp.cpp`; it is described from the code.

## Overview

The tool copies a programming problem from Polygon (Codeforces' problem-preparation system) into
the platform's PostgreSQL database and uploads its test files to cloud storage.

| Part | Where |
|---|---|
| Login and logout | `users/views.py`, `users/backends.py`, `users/templates/users/login.html` |
| The single working page | `problems/views.py` (`index`), `problems/templates/problems/index.html` |
| Polygon client, Redis cache, checker compilation | `problems/polygon_api.py` (`PolygonAPI`) |
| Storage interface and Azure provider | `problems/storage/` |
| Tables | `problems/models.py` (`Problem`, `ProblemTag`, `SampleTestCase`, `ProblemTestCase`), `users/models.py` (`User`) |

There are four URLs (`PolygonMigration/urls.py`, `problems/urls.py`, `users/urls.py`):

| URL | View | Purpose |
|---|---|---|
| `/` | `problems.views.index` | Fetch and all three migration actions |
| `/users/login/` | `users.views.login_view` | Login form |
| `/users/logout/` | `users.views.logout_view` | Logout |
| `/admin/` | Django admin | Browse and edit the tables |

Fetching and the three migration actions all post to `/`. The view decides what to do from which
form field is present (`problems/views.py:125-128`):

| Button on the page | Form (in `index.html`) | Field that selects the action |
|---|---|---|
| Fetch Problem | `fetchForm`, line 124 | only `problem_id` |
| Create/Update problem in Database | `migrate-db-form`, line 237 | `migrate_to_db=1` |
| Migrate Test Description to Database | `migrate-test-cases-form`, line 310 | `migrate_test_cases_to_db=1` |
| Migrate Test Cases to Azure | `migrate-azure-form`, line 250 | `migrate_to_azure=1` |

Whichever button is pressed, the view also runs the same "load the problem for display" steps
(`problems/views.py:234-329`), because the page is rendered again from scratch each time. Those
steps are described once, in flow 1.2, and referred to as the display block in the other flows.

## 1. User Flows

### 1.1 User login

**1. What the user does**
Opens the site. `/` is restricted to logged-in staff users
(`@user_passes_test(...)`, `problems/views.py:88`), so an anonymous visitor is redirected to
`/users/login/?next=/`. The user types an email and password and clicks **Login**.

**2. Data sent from the frontend**
`POST /users/login/` as a normal HTML form (`users/templates/users/login.html:23-33`):

| Field | Value |
|---|---|
| `csrfmiddlewaretoken` | CSRF token rendered into the form |
| `email` | the email typed |
| `password` | the password typed |

**3. Backend steps** (`users/views.py:8-23`, `login_view`)
1. If the request already belongs to a logged-in user, that user is logged out first (lines 9-10).
   Opening the login page therefore always ends the current session.
2. On POST, read `email` and `password` (lines 12-13).
3. Call `authenticate(request, username=email, email=email, password=password)` (line 14). Django
   tries the backends in `AUTHENTICATION_BACKENDS` (`PolygonMigration/settings.py:196-199`):
   first `users.backends.EmailBackend`, which finds the user by email, checks the password hash and
   checks `is_active` (`users/backends.py:5-16`); then Django's `ModelBackend`.
4. If a user is returned and `is_staff` is true, call `login(request, user)` and redirect to
   `problems:index`, which is `/` (lines 16-18). The `next` parameter is not used.
5. If the user is not staff, add the message "You do not have staff access." If authentication
   failed, add "Invalid email or password." In both cases the login page is rendered again
   (lines 19-23).

**4. External APIs called**
None.

**5. Database and storage**
- Read: `users_user` (lookup by email). The user model is custom, with the email as the login name
  (`users/models.py:25-56`, `AUTH_USER_MODEL = 'users.User'`).
- Write: on success, a row in `django_session` and the user's `last_login`.
- There is no sign-up page. Users are created with `python manage.py createsuperuser` or in `/admin/`.

**6. What the user sees**
- Success: the main page, "Hatsu: Problem Migrator", with "Welcome, first-name last-name" and a
  **Logout** button in the top bar and an empty "Enter Polygon Problem ID" box. The session lasts one
  day (`SESSION_COOKIE_AGE = 86400`, `settings.py:122`).
- Failure: the login page again with one of the two messages above.
- Logout: the **Logout** button posts to `/users/logout/` (`index.html:98`); `logout_view`
  (`users/views.py:25-27`) ends the session and redirects to the login page.

### 1.2 Fetching a problem from Polygon

**1. What the user does**
Types the Polygon problem ID (for example `631790`) and clicks **Fetch Problem**. JavaScript shows a
loading overlay and then submits the form (`index.html:418-426`).

**2. Data sent from the frontend**
`POST /` from `fetchForm` (`index.html:124-131`):

| Field | Value |
|---|---|
| `csrfmiddlewaretoken` | CSRF token |
| `problem_id` | the Polygon problem ID |

**3. Backend steps** (`problems/views.py`, `index`)
1. The decorator checks that the user is logged in and is staff (line 88).
2. Load every `ProblemTag` for the tags dropdown (lines 110-117).
3. Read the POST fields (lines 125-131) and create a `PolygonAPI` client (line 142).
4. Look for a `Problem` with this `polygon_id` (line 146). If one exists, its tags and difficulty
   are put in the page data, and the main solution is fetched from Polygon: update the working
   copy, list the solutions, pick the one tagged `MA` (main), or the first one, and download its
   source (lines 149-184). A failure here is logged and the solution is left empty.
5. Everything after this runs inside one `try` and one database transaction (lines 186-187).
6. Display block, part 1: problem info. `api.get_problem_info` (line 235).
7. Display block, part 2: statement. `api.download_and_extract_package` (line 239;
   `problems/polygon_api.py:129-241`) lists the packages, picks the `standard` package with the
   highest revision, downloads the zip, extracts it into a temporary folder, finds `problem.html`,
   reads it and deletes the folder. `parse_problem_html` (`problems/views.py:19-86`) then takes the
   title, legend, input specification, output specification and notes out of that HTML.
8. Test cases: because no migration field is present, the tests are always downloaded again.
   `api.get_all_test_cases` (`problems/polygon_api.py:351-407`) lists the tests of the testset
   named `tests` and downloads the input and the answer of each one. A test whose download fails is
   kept with empty input and output and a warning in the log. The list is then cached in Redis for
   30 minutes (`problems/views.py:256-259`).
9. Build the table rows with 50-character previews (lines 263-278).
10. Work out the remaining fields (lines 283-308): title from the statement (or the Polygon name),
    slug with `slugify(title)`, time and memory limit from the problem info, checker name with
    `std::` and `.cpp` removed (anything not in the standard list becomes `custom`), custom-checker
    details, and the test count. `constraints` and `editorial` are set to empty text.
11. Put it all in `context['fetched_problem']` (lines 313-329) and render `problems/index.html`
    (line 569).

If anything in steps 6 to 10 raises an error, the page shows "Migration failed and all changes have
been rolled back. Reason: ..." and the cached test cases for this problem are cleared (lines 553-560).

**4. External APIs called** (Polygon, in order)

| Call | Purpose |
|---|---|
| `problem.updateWorkingCopy`, `problem.solutions`, `problem.viewSolution` | Only when the problem is already in the database: main solution |
| `problem.info` (twice) | Limits; the second call is inside the package download |
| `problem.packages`, `problem.package` | Find and download the standard package |
| `problem.tests` | List of tests |
| `problem.testInput`, `problem.testAnswer` | Once per test |
| `problem.checker` (twice) | Checker name, and custom-checker check |
| `problem.tests` (again) | Test count |

That is 8 calls plus 2 per test for a new problem, and 3 more for one already in the database.
Problem 631790 (15 tests) took about 30 seconds.

**5. Database and storage**
- Database read: `ProblemTag` (all), `Problem` by `polygon_id`, and that problem's tags.
- Database write: none.
- Redis write: `polygon_migration_test_cases_{polygon_id}_count` and one
  `polygon_migration_test_cases_{polygon_id}_test_{n}` key per test, each expiring after 30 minutes
  (`problems/polygon_api.py:786-831`).
- Cloud storage: not used.

**6. What the user sees**
- "Fetched Problem: title (Polygon ID: id)".
- A table with "Database Problem ID" and "Algopath Link": "Please migrate to database first." for a
  new problem, or the database ID and link for an existing one.
- Slug, a difficulty dropdown, the tags box, time limit, memory limit, checker type, test case count.
- Problem statement, input format, output format and notes. These are shown as raw HTML text with
  `$$$...$$$` math markers, not as formatted text.
- The buttons. For a new problem only **Create/Update problem in Database** is enabled.
- "All Test Cases (N total)": index, input, output, description and whether it is a sample, with a
  **View Full** button for long values.
- "Main Correct Solution": the source for an existing problem, otherwise "Please migrate the problem
  to the database first."

### 1.3 Migrating a problem to the database

**1. What the user does**
After a fetch, chooses a difficulty (required), optionally selects or types tags, and clicks
**Create/Update problem in Database**.

**2. Data sent from the frontend**
`POST /` from `migrate-db-form` (`index.html:237-248`):

| Field | Value |
|---|---|
| `csrfmiddlewaretoken` | CSRF token |
| `problem_id` | the Polygon problem ID (hidden) |
| `migrate_to_db` | `1` (hidden) |
| `difficulty` | `easy`, `medium` or `hard`; a hidden field that JavaScript copies from the dropdown (`index.html:392-399`) |
| `tags` | one hidden field per selected tag, built on submit by `updateHiddenInputs` (`index.html:597`) |

Before submitting, JavaScript stops the form and shows an alert if no difficulty is selected
(`index.html:402-415`). The view also reads a `new_tag` field (`problems/views.py:131`), but the
page never sends one.

**3. Backend steps** (`problems/views.py`, `index`)
1. Steps 1 to 5 of flow 1.2 (access check, tags, existing problem and its main solution, transaction).
2. The display block runs again (problem info, package download, parsing), so the values saved are
   freshly read from Polygon. Test cases come from the Redis cache this time; if the cache has
   expired they are downloaded again and cached (lines 247-254).
3. If `difficulty` is empty, stop with "Please select a difficulty level before migrating to
   database." (lines 334-336).
4. Look for a `Problem` with this `polygon_id` (line 340).
   - Found: overwrite its fields and save (lines 344-358).
   - Not found: create it (lines 368-383).

   Fields written: `polygon_id`, `title`, `slug`, `difficulty`, `problem_statement`, `input_format`,
   `output_format`, `constraints` (empty), `editorial` (empty), `time_limit`, `memory_limit`,
   `checker_type`, `test_case_count`, `notes`.
5. Tags: remove all tags from the problem, then for each submitted name get or create a `ProblemTag`
   and attach it (lines 396-408).
6. Read the test cases from Redis again, with the same fallback (lines 426-434).
7. Sample test cases: take the tests marked as samples, strip trailing whitespace, and write them to
   `SampleTestCase` in order. Existing rows are updated by position and extra ones are created;
   samples with empty input or output are skipped (lines 439-463). Sample text is stored in full.
8. Reload the problem and fetch the main solution from Polygon (lines 466-495).
9. The transaction commits when the block ends. On any error it rolls back, the page shows the
   "Migration failed..." message and the cached test cases are cleared (lines 553-560).

**4. External APIs called**
Polygon only: the display-block calls of flow 1.2 without the per-test downloads (`problem.info`
twice, `problem.packages`, `problem.package`, `problem.checker` twice, `problem.tests`), plus
`problem.solutions` and `problem.viewSolution`. For a problem already in the database the
existing-problem step adds `problem.updateWorkingCopy` and a second solution lookup.

**5. Database and storage**
- Read: `Problem`, `ProblemTag`, `SampleTestCase`.
- Write: `problems_problem` (insert or update), `problems_problemtag` (new tags), the problem-to-tag
  link table, `problems_sampletestcase`.
- Redis: read the cached test cases.
- Cloud storage: not used.

**6. What the user sees**
- A blue "Database Operation" box: "Problem 'title' created in database successfully." or
  "... updated in database successfully.", with "Custom checker 'name' detected." added when there
  is one.
- "Database Problem ID" now shows the new ID and "Algopath Link" shows
  `https://www.algopath.ai/problems/{slug}`.
- The saved tags are shown as selected, the two test-case buttons become enabled, and the main
  solution appears.
- On failure, a red "Error" box with the reason.

### 1.4 Migrating test cases to the database

**1. What the user does**
Clicks **Migrate Test Description to Database**, below the test case table. The button is disabled
until the problem exists in the database.

**2. Data sent from the frontend**
`POST /` from `migrate-test-cases-form` (`index.html:310-315`):

| Field | Value |
|---|---|
| `csrfmiddlewaretoken` | CSRF token |
| `problem_id` | the Polygon problem ID (hidden) |
| `migrate_test_cases_to_db` | `1` (hidden) |

**3. Backend steps** (`problems/views.py`, `index`)
1. Steps 1 to 5 of flow 1.2.
2. The display block runs again; test cases come from the Redis cache, or from Polygon if the cache
   is empty.
3. Find the `Problem` by `polygon_id`. If it does not exist, stop with "Please migrate the problem
   to the database first." (lines 498-502).
4. Read the test cases from Redis again, with the same fallback (lines 505-513).
5. Load the problem's existing `ProblemTestCase` rows in `order` (line 516).
6. For each test, in order (lines 518-549):
   - strip trailing whitespace from input and output;
   - skip the test if either is empty;
   - keep only the first 260 characters of each;
   - update the existing row at the same position, or create a new row, with `input`, `output`,
     `is_sample`, `description` and `order`. `order` counts saved rows from 1.
7. Set the success message (lines 550-551). The transaction commits when the block ends.

The rows stored here are short previews of the tests, not the full data; the full files are only
in cloud storage (flow 1.5). This step never deletes a row.

**4. External APIs called**
Polygon only, and only because of the display block and the existing-problem step: no call is
needed for the test cases themselves when they are cached.

**5. Database and storage**
- Read: `Problem`, `ProblemTestCase`.
- Write: `problems_problemtestcase` (update or insert). `created_at` and `updated_at` are set by
  the model.
- Redis: read the cached test cases.
- Cloud storage: not used.

**6. What the user sees**
A green "Success" box: "Test cases description migrated to database Successfully." The rest of the
page is rendered again as after a fetch. The message does not say how many rows were written.

### 1.5 Uploading test cases to cloud storage

**1. What the user does**
Clicks **Migrate Test Cases to Azure**, next to the create button. It is disabled until the problem
exists in the database.

**2. Data sent from the frontend**
`POST /` from `migrate-azure-form` (`index.html:250-255`):

| Field | Value |
|---|---|
| `csrfmiddlewaretoken` | CSRF token |
| `problem_id` | the Polygon problem ID (hidden) |
| `migrate_to_azure` | `1` (hidden) |

**3. Backend steps**
1. Steps 1 to 5 of flow 1.2.
2. Find the `Problem` by `polygon_id` (`problems/views.py:193`). If it does not exist, show an
   error and stop (lines 194-197). Its database ID is used for the file paths from here on.
3. Delete Redis keys matching `oj_dev_with_redis_storage_test_cases_{database id}*` (line 207;
   `problems/polygon_api.py:758-784`). This application does not write those keys.
4. Ask Polygon for the checker; if it is a custom one, remember its name for the messages
   (lines 210-213).
5. `get_storage()` returns the provider chosen by `STORAGE_PROVIDER`
   (line 217; `problems/storage/__init__.py:36-46`).
6. `api.migrate_test_cases_to_storage(polygon_id, storage, database id)`
   (line 218; `problems/polygon_api.py:693-756`):
   1. read the test cases from Redis, or download and cache them if the cache is empty;
   2. `storage.delete_problem_files(id)`: list every file under `test_cases/{id}/` and delete it;
   3. for each test, numbered from 1 by position: if it has both input and output, upload two
      files with `storage.upload_test_case`; otherwise log a warning and skip it;
   4. `upload_custom_checker` (`problems/polygon_api.py:570-691`): if the checker is custom, download
      its source, compile it with `g++ -std=gnu++17 -O2` and upload the binary as `custom_checker`
      (`custom_checker.exe` on Windows). If compiling fails, the source is uploaded as
      `custom_checker.cpp`. Errors in this part are only logged.
7. Set the success message (`problems/views.py:229-232`).
8. The display block then runs, as in every flow.

A storage error raises `StorageError`; the page then shows "Migration failed and all changes have
been rolled back. Reason: ...". Files that were already deleted or uploaded are not restored.

**4. External APIs called**
- Polygon: `problem.checker`, the display-block calls, and for a custom checker `problem.viewFile`.
  `problem.tests`, `problem.testInput` and `problem.testAnswer` only if the cache is empty.
- Azure Blob Storage, through the `azure-storage-blob` SDK: list blobs with the problem's prefix,
  delete each one, then upload two blobs per test (`problems/storage/azure_blob.py:53-71`).

**5. Database and storage**
- Database read: `Problem` (to get the database ID). No database write.
- Redis: read the cached test cases; delete the keys from step 3.
- Cloud storage: delete everything under `test_cases/{id}/`, then write `{NN}` and `{NN}.a` for each
  test, and the checker file if there is one. See section 2.2 for the layout.

**6. What the user sees**
A green "Success" box: "Test cases migrated to Azure Blob Storage successfully.", with "Custom
checker 'name' was also compiled and uploaded." added for a custom checker. The message does not
say how many files were uploaded. For problem 631790 the result was 30 blobs, `test_cases/2/01` to
`15` and `01.a` to `15.a`, confirmed in the storage listing.

## 2. External Integrations

### 2.1 Polygon API (endpoints used, request authentication)

All Polygon access goes through `PolygonAPI` in `problems/polygon_api.py`.

**Base URL and transport**
`https://polygon.codeforces.com/api/{method}` (`API_URL`, line 26). Every call is an HTTP POST with
form-encoded parameters, made with `requests.post` (lines 96 and 187).

**Credentials**
`POLYGON_API_KEY` and `POLYGON_API_SECRET` are read from the environment (`.env`) in
`PolygonMigration/settings.py:124-125`. The application refuses to start if either is missing
(lines 127-128). The key is sent with every request; the secret is never sent, it is only used to
sign.

**Request signing** (`_generate_api_sig`, lines 35-68, used by `_make_request`, lines 70-114)
1. Add `apiKey` and `time` (current Unix time in seconds) to the method's parameters.
2. Sort the parameters by name and join them as `name=value&name=value`.
3. Make a random 6-character prefix of lowercase letters and digits.
4. Build the text `{prefix}/{method}?{parameters}#{secret}`.
5. Take its SHA-512 hash in hexadecimal.
6. `apiSig` is the prefix followed by the hash.

The request then carries the method's parameters plus `apiKey`, `time` and `apiSig`. Polygon
repeats the calculation with its copy of the secret and rejects the request if the result differs.

**Responses and errors**
- JSON methods return `{"status": "OK", "result": ...}`; the client returns `result`. With
  `"status": "FAILED"` it raises `Polygon API Error: {comment}` (lines 103-107).
- Text methods (`_make_plain_request`, lines 116-127) return the response body as it is.
- An HTTP error status raises `HTTP Request Error: ...` (lines 113-114).
- There is no retry and no timeout. During this work Polygon answered HTTP 429 (Too Many Requests)
  when the same problem was fetched twice about ten seconds apart.

**Endpoints used**

| Method | Called from | Parameters besides `problemId` | Returns | Used for |
|---|---|---|---|---|
| `problem.info` | `get_problem_info`, line 254 | none | JSON | time limit, memory limit |
| `problem.packages` | line 155 | none | JSON list | choose the newest `standard` package |
| `problem.package` | line 187 | `packageId`, `type` | zip file | `problem.html` with the statement |
| `problem.tests` | lines 304 and 364 | `testset` (`tests`) | JSON list | test index, sample flag, description, count |
| `problem.testInput` | line 383 | `testset`, `testIndex` | text | input of one test |
| `problem.testAnswer` | line 390 | `testset`, `testIndex` | text | expected output of one test |
| `problem.checker` | line 421, `problems/views.py:292` | none | JSON string | checker name |
| `problem.viewFile` | lines 452-482 | `type` (`source` or `resource`), `name` | text | source of a custom checker |
| `problem.updateWorkingCopy` | `problems/views.py:160` | none | JSON | update the problem's working copy on Polygon, before the solutions are read |
| `problem.solutions` | `problems/views.py:162`, `:473` | none | JSON list | find the main solution (tag `MA`) |
| `problem.viewSolution` | `problems/views.py:177`, `:488` | `name` | text | source of the main solution |

`PolygonAPI` also has `get_statements` (`problem.statements`), `get_test_script` (`problem.script`),
`get_problem_files` (`problem.files`) and `get_file_content`; none of them is called by any flow.

**What the tool needs on the Polygon side**
The problem must have a built `standard` package, because the statement is read from the package,
and its tests must be in the testset named `tests`. Without a package, the fetch stops with
"Error downloading/extracting package: No packages available for this problem".

**Cache between the steps**
Fetched test cases are kept in Redis for 30 minutes so the migration steps do not download them
again (`store_test_cases_in_redis`, `get_test_cases_from_redis`, `clear_test_cases_from_redis`,
lines 786-921). Keys: `polygon_migration_test_cases_{polygon_id}_count` and
`..._test_{n}`. Each value holds the test's index, input, output, description and sample flag.
The connection settings are `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` and `REDIS_SSL`.

### 2.2 Cloud storage (file naming and organization)

**Structure of the code**

| File | Contents |
|---|---|
| `problems/storage/base.py` | `TestCaseStorage`, the interface every provider implements, the path rules, and `StorageError` |
| `problems/storage/azure_blob.py` | `AzureBlobStorage`, the Azure provider |
| `problems/storage/__init__.py` | `get_storage()`, which returns the provider named by `STORAGE_PROVIDER` |

A provider implements three operations: `upload_file(path, data)`, `list_files(prefix)` and
`delete_file(path)`. The shared methods `upload_test_case`, `upload_checker` and
`delete_problem_files` are built on those three in the base class, so the migration code
(`PolygonAPI.migrate_test_cases_to_storage`) never refers to a specific provider. Adding a provider
means one new module and one line in `_PROVIDERS`.

**File naming**
All files of one problem are under one prefix. The paths are defined once, in
`problems/storage/base.py:18-32`:

| File | Path | Example |
|---|---|---|
| Test input | `test_cases/{problem_id}/{test_number}` | `test_cases/2/01` |
| Test output | `test_cases/{problem_id}/{test_number}.a` | `test_cases/2/01.a` |
| Custom checker | `test_cases/{problem_id}/custom_checker` (`.exe` on Windows, `.cpp` if not compiled) | `test_cases/2/custom_checker` |

- `problem_id` is the database ID of the problem (`Problem.id`), not the Polygon ID. That is why
  the problem has to be saved to the database before its tests can be uploaded.
- `test_number` is the position of the test in the list, starting at 1, written with at least two
  digits (`01`, `02`, ... `99`, `100`).
- Input files have no extension; output files end in `.a`.
- The content is the text Polygon returned, encoded as UTF-8 and otherwise unchanged. Nothing is
  truncated here, unlike the database rows of flow 1.4.

Example, problem 631790 saved as database problem 2 with 15 tests:

```
testcases                      (container)
└── test_cases/
    └── 2/
        ├── 01
        ├── 01.a
        ├── 02
        ├── 02.a
        ...
        ├── 15
        └── 15.a
```

**Behaviour**
- Each upload replaces the problem's files: everything under the problem's prefix is deleted first,
  then the current tests are uploaded. Uploads overwrite a file of the same name.
- A test without input or without output is skipped. Its number is not reused, so the numbering has
  a gap at that position.
- Problems do not affect each other, because each has its own prefix.

**Configuration** (environment variables, read in `PolygonMigration/settings.py:130-140`)

| Variable | Meaning |
|---|---|
| `STORAGE_PROVIDER` | Which provider to use. Default `azure`. An unknown name raises `StorageError` listing the supported ones. |
| `AZURE_CONTAINER_NAME` | The container that holds the files. It must already exist. |
| `AZURE_STORAGE_CONNECTION_STRING` | Preferred way to authenticate (account key or SAS). |
| `AZURE_STORAGE_ACCOUNT_URL`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_USERNAME`, `AZURE_PASSWORD` | Used together, only when no connection string is set (Azure AD username and password). |

No credential is written in the code. `.env.example` lists the variables, and the connection string
is hidden on Django's error pages by `PolygonMigration/debug.py`.

**Azure operations used** (`problems/storage/azure_blob.py`)

| Interface method | Azure SDK call |
|---|---|
| `upload_file` | `ContainerClient.upload_blob(name, data, overwrite=True)` |
| `list_files` | `ContainerClient.list_blobs(name_starts_with=prefix)` |
| `delete_file` | `ContainerClient.delete_blob(name)` |

Every Azure error is turned into `StorageError` with the path in the message, so the view can show
it to the user.
