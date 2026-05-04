import argparse
import base64
import copy
import fnmatch
import json
import sys
import urllib.error
import urllib.request
from collections import OrderedDict
from pathlib import Path

REF_PREFIX = "#/components/schemas/"
OPENAPI_URL = "https://api.bubblemaps.io/openapi.json"


def endpoint_matches(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def collect_schema_refs(obj, refs: set[str]) -> None:
    if isinstance(obj, dict):
        ref = obj.get("$ref")
        if isinstance(ref, str) and ref.startswith(REF_PREFIX):
            refs.add(ref[len(REF_PREFIX) :])

        for value in obj.values():
            collect_schema_refs(value, refs)

    elif isinstance(obj, list):
        for item in obj:
            collect_schema_refs(item, refs)


def load_spec_from_url(password: str) -> dict:
    credentials = f"admin:{password}".encode("utf-8")
    auth_header = base64.b64encode(credentials).decode("ascii")

    request = urllib.request.Request(
        OPENAPI_URL,
        headers={
            "Authorization": f"Basic {auth_header}",
            "Accept": "application/json",
            "User-Agent": "openapi-filter-script/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Failed to fetch OpenAPI spec: HTTP {e.code}\n{body}"
        ) from e


def load_spec_from_file(path: str) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def prune_unused_schemas(spec: dict) -> tuple[dict, list[str], list[str]]:
    components = spec.get("components", {})
    schemas = components.get("schemas", {})

    if not schemas:
        return spec, [], []

    used = set()
    collect_schema_refs(spec.get("paths", {}), used)

    changed = True
    while changed:
        changed = False

        for schema_name in list(used):
            schema = schemas.get(schema_name)
            if schema is None:
                continue

            before = len(used)
            collect_schema_refs(schema, used)

            if len(used) > before:
                changed = True

    all_schema_names = set(schemas.keys())
    kept = sorted(used & all_schema_names)
    removed = sorted(all_schema_names - used)

    components["schemas"] = {
        name: schema for name, schema in schemas.items() if name in used
    }

    return spec, kept, removed


def reorder_top_level_keys(spec: dict) -> OrderedDict:
    ordered = OrderedDict()

    if "openapi" in spec:
        ordered["openapi"] = spec["openapi"]

    ordered["info"] = spec["info"]
    ordered["servers"] = spec["servers"]

    for key, value in spec.items():
        if key not in {"openapi", "info", "servers"}:
            ordered[key] = value

    return ordered


def filter_openapi_spec(
    spec: dict,
    patterns: list[str],
    version: str,
) -> tuple[dict, list[str], list[str], list[str], list[str]]:
    filtered = copy.deepcopy(spec)

    original_paths = set(filtered.get("paths", {}).keys())

    filtered_paths = {
        path: path_item
        for path, path_item in filtered.get("paths", {}).items()
        if endpoint_matches(path, patterns)
    }

    filtered["paths"] = filtered_paths

    kept_paths = sorted(filtered_paths.keys())
    removed_paths = sorted(original_paths - set(kept_paths))

    filtered, kept_schemas, removed_schemas = prune_unused_schemas(filtered)

    filtered["info"] = {
        "title": "Bubblemaps Data API",
        "version": version,
    }

    filtered["servers"] = [
        {
            "url": "https://api.bubblemaps.io",
        }
    ]

    filtered = reorder_top_level_keys(filtered)

    return filtered, kept_paths, removed_paths, kept_schemas, removed_schemas


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Filter the Bubblemaps OpenAPI spec and list kept/removed endpoints and schemas."
    )

    parser.add_argument("output", help="Output OpenAPI JSON file")

    parser.add_argument(
        "--version",
        required=True,
        help='Version to set in info.version, e.g. "0.2.0"',
    )

    parser.add_argument(
        "--pattern",
        action="append",
        required=True,
        help='Endpoint pattern to keep, e.g. "/chains", "/map/*", "/v0/*". Can be used multiple times.',
    )

    parser.add_argument(
        "--password",
        help='Basic auth password for https://api.bubblemaps.io/openapi.json. User is always "admin".',
    )

    parser.add_argument(
        "--input-file",
        help="Optional local OpenAPI JSON file. If provided, the script will not fetch from the URL.",
    )

    args = parser.parse_args()

    if args.input_file:
        spec = load_spec_from_file(args.input_file)
    else:
        if not args.password:
            print(
                "Error: --password is required unless --input-file is provided.",
                file=sys.stderr,
            )
            sys.exit(1)

        spec = load_spec_from_url(args.password)

    filtered, kept_paths, removed_paths, kept_schemas, removed_schemas = (
        filter_openapi_spec(
            spec=spec,
            patterns=args.pattern,
            version=args.version,
        )
    )

    output_path = Path(args.output)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)

    print(f"\nKept endpoints ({len(kept_paths)}):")
    for path in kept_paths:
        print(f"  + {path}")

    print(f"\nRemoved endpoints ({len(removed_paths)}):")
    for path in removed_paths:
        print(f"  - {path}")

    print(f"\nKept schemas ({len(kept_schemas)}):")
    for schema in kept_schemas:
        print(f"  + {schema}")

    print(f"\nRemoved schemas ({len(removed_schemas)}):")
    for schema in removed_schemas:
        print(f"  - {schema}")

    print(f"\nFiltered spec written to: {output_path}")


if __name__ == "__main__":
    main()
