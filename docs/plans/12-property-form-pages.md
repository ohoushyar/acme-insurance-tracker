# Step 12: Property add/edit pages

This plan splits the inline property form off `/properties`. No API
change.

## Decisions (surfaced, not silent)

| Topic | Choice | Why |
|---|---|---|
| Add | `/properties/new` from a **+** control (`aria-label="Add property"`) | List stays a list. |
| After save | `navigate("/properties")` | List reloads on mount. |
| Edit | `/properties/:id/edit` | The list form was shared with add; it cannot stay. |
| Route order | `/properties/new` before `/:id/edit` | Avoid treating `new` as an id. |

## Architecture

```
/properties          list + + + delete
/properties/new      Label / Address / Stated value → POST → list
/properties/:id/edit same fields → PATCH → list
```

Shared fields live in
[frontend/src/components/PropertyFormFields.tsx](../../frontend/src/components/PropertyFormFields.tsx).
Edit loads `GET /api/v1/properties/{id}`.

## Tests

[frontend/src/portfolio.test.tsx](../../frontend/src/portfolio.test.tsx):
list has no Label field; create via `/properties/new` then the row
appears on the list; edit PATCH then return.
