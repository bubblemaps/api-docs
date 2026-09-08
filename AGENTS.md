# Agent instructions for this docs repo

Mintlify documentation for Bubblemaps B2B (iFrame + Data API). Site config is `docs.json`. The published OpenAPI spec is `openapi.json` at the repo root; Mintlify uses it for interactive API pages via `openapi:` frontmatter.

When updating Data API docs after a schema change, **read this file first**, then match the tone and structure of existing MDX pages. Changelog layout and wording are defined by the pages under `data/api/changelog/`, not by restating them here.

## OpenAPI update workflow

1. Diff `openapi-old.json` vs `openapi.json`, and read `openapi-deprecated.json`. Typical checks:
   - paths added / removed / still present but `deprecated: true`
   - parameters, request bodies, response codes
   - schema properties added / removed / made nullable / required-list changes
   - enums (especially `ChainIdV0`)
   - `info.version`
2. Update MDX, `docs.json` navigation, redirects, and changelog to match. Follow existing page style (credit `Info`, Warnings, Notes, Check marks, short prose).
3. Do not invent credit costs, parameters, or behavior that are not in the spec or already documented. If a new endpoint has no credit cost in the spec, ask.

Live endpoint pages use frontmatter like `openapi: "GET /v0/tokens/map/{chain}/{token_address}"`. That operation must exist in `openapi.json` or the playground breaks.

## Changelog

Add a dated page `data/api/changelog/YYYY-MM-DD.mdx`, list it first in the Changelog group in `docs.json`, and add a short summary at the top of `data/api/changelog/index.mdx`.

Copy structure from the latest changelog page (version line, Deprecated Features first, then New Features, removals last, Mintlify `Check` / `Warning`). Put `API version \`x.y.z\`.` at the top, using `info.version` from the new spec.

**Do not rewrite past changelog wording or announced dates.** When something announced there is later removed, append this at the **end of the existing warning box** (see `data/api/changelog/2026-04-29.mdx`):

```mdx
[Edit: See the [YYYY-MM-DD](/data/api/changelog/YYYY-MM-DD) notes for the actual removal.]
```

Index summaries for old releases stay as they were. Mention new features before removals in both the new page and its index blurb.

## Endpoint and field lifecycle

There are three states. **As of 0.3.0 there are no deprecated endpoints** — do not create empty `deprecated` nav groups or folders “just in case”.

### Live

Page lives next to its resource (`data/api/tokens/`, `data/api/chains/`, …) and is listed in `docs.json`. Document current behavior only.

### Deprecated (still in the API)

Move the page to `data/api/deprecated/` (keep a stable slug). Keep `openapi:` so the playground still works. Add a `Warning` with the announced removal date and the replacement. Changelog the deprecation.

List it in `docs.json` under a **Deprecated** group in Data API. The group should appear in the sidebar when it has pages, **collapsed by default** (`"expanded": false`). Do not create an empty Deprecated group or folder when there are none.

Redirect the previous live URL:

```json
{
  "source": "/data/api/tokens/example",
  "destination": "/data/api/deprecated/example"
}
```

Deprecated **response fields** that `prepare-openapi-schema.py` strips should still be mentioned on the live page (warning + link to changelog) until they are actually removed. Use `openapi-deprecated.json` for the field list and replacements.

### Removed

Do not delete the docs URL. Move the page to a tombstone and redirect.

1. Move `data/api/deprecated/<page>.mdx` → `data/api/removed/<page>.mdx` (or from the live folder if it was never deprecated). Keep a stable slug.
2. Replace body with a short “this has been removed, use X” page. Drop `openapi:` (the operation is gone from the spec). Set `hidden: true` so it stays out of the sidebar and search.
3. Remove it from `docs.json` navigation. If the Deprecated group is now empty, remove that group too. Do **not** add a Removed group to the menu.
4. Add a permanent redirect in `docs.json` from the **previous file URL** to the new one:

```json
{
  "source": "/data/api/deprecated/example",
  "destination": "/data/api/removed/example"
}
```

Keep any older redirects that already pointed at the deprecated URL (or retarget them to `/data/api/removed/...`). Only redirect paths that actually existed. Extra aliases are for historical hrefs that already shipped (for example the April 2026 changelog uses `/deprecated/get-map-data`).

5. Record the removal in the new changelog (after new features). Link tombstones from that changelog. Append the `[Edit: …]` line on the original deprecation changelog.
6. On **live** replacement pages, remove “this field is deprecated” warnings. History lives in the changelog, not on current endpoint docs.

Tombstone examples: `data/api/removed/get-supported-chains.mdx`, `data/api/removed/get-map-data.mdx`.

## MDX and `{path}` parameters

`{chain}` and `{token_address}` are MDX expressions. Unescaped, they vanish (`/v0/tokens/map//`).

- YAML `description`: HTML entities, e.g. `&#123;chain&#125;`
- Body: JS strings, e.g. `<code>{'GET /v0/tokens/map/{chain}/{token_address}'}</code>`

`openapi:` frontmatter values are spec paths, not MDX prose; leave `{chain}` as-is there.

## Other conventions

- **Beta** endpoints: no sidebar `tag` (it wraps the nav). Use `<Warning>This endpoint is in **beta**. Deal with caution.</Warning>` on the page; mention beta in the changelog. Example: `data/api/tokens/screenshot.mdx`.
- Credit costs live in MDX (`<Info>**Credit cost:** …</Info>`), not in OpenAPI.
- Prefer `/data/api/...` links in new content. Do not “fix” historical changelog hrefs; add redirects if those old paths must keep working.
- iFrame docs (`iframe/`) are a separate product. Only touch them when the change is actually about the iFrame.
