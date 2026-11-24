# Code Issues

The three highest-priority code issues, ranked from highest to lowest.

| Type | Critical | High | Medium | Low | Total |
|------|----------|------|--------|-----|-------|
| Code Issues | 0 | 3 | 0 | 0 | 3 |

All three are in the starter code. Each one was tested by running the real view code against a
throwaway test database, with Polygon and storage replaced by fakes.

---

## Code Issues

### [C1] A tag name is shown on the page as code, not as text (stored XSS)

**Severity**: High

**Location**: `problems/templates/problems/index.html:365-366` and `:575`

**Description**:
A tag name is typed by the user and saved as it is. The page then puts it back without making it
safe:

```
var allTags = {{ all_tags_json|safe }};          // line 365: |safe turns escaping off
tagElement.innerHTML = tagName + '<span ...';    // line 575: read by the browser as HTML
```

So if a tag name contains HTML or JavaScript, the browser runs it.

Tested: the tag `<img src=x onerror=alert(1)>` was saved with a problem. The alert ran when the
problem was opened again. A tag containing `</script><script>...` ran on every page load.

**Impact**:
- One staff user can make code run in the browser of every other user who opens the tool. That
  code works with the other user's login.
- One bad tag can break the page for everyone until the tag is deleted.
- Even a normal tag with an apostrophe, like `kadane's algorithm`, breaks its own remove button.

**Suggested Fix**:
- Use Django's `json_script` filter to pass the tags to JavaScript, and remove `|safe`.
- Build the tag element with `textContent`, not `innerHTML`.
- Check tag names on the server and allow only letters, digits, spaces and a few symbols.

---

### Also found and fixed: clicking a tag in the list often did not select it

This is a smaller bug in the same tag box. It is not counted in the top three. It is already fixed
in commit `cf96351`.

**Location**: `problems/templates/problems/index.html:381-383`

**Description**:
The tag list was hidden 200 ms after the search box lost focus:

```js
searchInput.addEventListener('blur', function() {
    setTimeout(hideDropdown, 200);
});
```

The search box loses focus as soon as the mouse is pressed on a tag, but the browser sends the
click only when the mouse is released. If the click took longer than 200 ms, the list was already
hidden, so nothing was selected and no error was shown.

**Fix** (commit `cf96351`):
One line was added. It keeps the focus in the search box while the mouse is pressed inside the
list, so the list stays open until the click is done:

```js
dropdown.addEventListener('mousedown', function(e) { e.preventDefault(); });
```

Tested with real mouse clicks: before the fix a slow click selected nothing; after the fix the tag
is selected and the list stays open. A click outside the list still closes it.

---

### [C2] The page says the custom checker was "compiled and uploaded" even when it was not

**Severity**: High

**Location**: `problems/views.py:229-232`

**Description**:
A custom checker is a small program that decides if an answer is correct. When test cases are
moved to storage, the checker must be compiled and uploaded too. The success message is built like
this:

```python
if custom_checker_info:
    success_message += f" Custom checker '{custom_checker_info['name']}' was also compiled and uploaded."
```

The condition only checks that the problem has a custom checker. It does not check the result. The
function that does the work (`upload_custom_checker`, `problems/polygon_api.py:570`) returns
nothing and only writes a log line when it fails.

Tested in three failure cases: no compiler on the machine, checker source could not be downloaded,
and upload failed. The page showed the same "compiled and uploaded" message every time.

**Impact**:
- The database says the problem uses a custom checker, but storage has no working checker.
- The person migrating is told it worked, so nobody knows until submissions are judged wrongly or
  fail.
- Problems with more than one correct answer need a custom checker, so this is a normal case.

**Suggested Fix**:
- Make `upload_custom_checker` return what happened, or raise an error when it fails.
- Build the message from that result. Show an error if the checker was not uploaded.

---

### [C3] When a Polygon call fails, the problem is saved with 0 test cases

**Severity**: High

**Location**: `problems/polygon_api.py:303-311` and `problems/views.py:308`

**Description**:
The function that asks Polygon for the list of tests hides every error and returns an empty list:

```python
try:
    tests = self._make_request('problem.tests', {...})
    return tests
except Exception:
    return []
```

The view counts that list and saves the number as `test_case_count`. So when the call fails, the
count becomes 0, and the code cannot tell "the call failed" from "the problem has no tests".

Tested: a problem was saved with 15 tests. It was saved again while this call returned HTTP 429
(too many requests). The page said "updated in database successfully", and the row had
`test_case_count = 0`, while the same page listed 15 tests.

**Impact**:
- Wrong data is saved in the database: 0 tests for a problem that has 15.
- The user sees the normal success message, so nothing warns them.
- Polygon does return HTTP 429 when calls come too fast, so this can happen in normal use.

**Suggested Fix**:
- Remove the `try/except`, so a failed call stops the save and shows an error.
- Better: count the test list the view has already loaded, and do not call Polygon a second time.

---
