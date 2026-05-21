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


def schema_ref_name(schema: dict) -> str | None:
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith(REF_PREFIX):
        return ref[len(REF_PREFIX) :]
    return None


def resolve_schema(
    spec: dict,
    schema: dict,
    seen_refs: set[str] | None = None,
) -> dict:
    if seen_refs is None:
        seen_refs = set()

    while isinstance(schema, dict) and "$ref" in schema:
        name = schema_ref_name(schema)
        if name is None or name in seen_refs:
            break
        seen_refs.add(name)
        schema = spec.get("components", {}).get("schemas", {}).get(name, schema)
        if not isinstance(schema, dict):
            break

    return schema if isinstance(schema, dict) else {}


def collect_deprecated_fields_in_schema(
    spec: dict,
    schema: dict,
    path_prefix: str = "",
    seen_refs: set[str] | None = None,
    enclosing_schema: str | None = None,
) -> list[dict]:
    if seen_refs is None:
        seen_refs = set()

    ref_name = schema_ref_name(schema)
    if ref_name:
        enclosing_schema = ref_name

    schema = resolve_schema(spec, schema, seen_refs.copy())
    found: list[dict] = []

    for prop_name, prop_schema in schema.get("properties", {}).items():
        if not isinstance(prop_schema, dict):
            continue

        field_path = f"{path_prefix}.{prop_name}" if path_prefix else prop_name
        prop_resolved = resolve_schema(spec, prop_schema, seen_refs.copy())
        prop_ref_name = schema_ref_name(prop_schema)
        field_schema = prop_ref_name or enclosing_schema

        if prop_schema.get("deprecated") or prop_resolved.get("deprecated"):
            found.append(
                {
                    "field": field_path,
                    "property": prop_name,
                    "schema": field_schema,
                    "description": prop_schema.get("description")
                    or prop_resolved.get("description"),
                }
            )

        found.extend(
            collect_deprecated_fields_in_schema(
                spec,
                prop_schema,
                field_path,
                seen_refs.copy(),
                prop_ref_name or enclosing_schema,
            )
        )

    for composite_key in ("anyOf", "oneOf", "allOf"):
        for sub_schema in schema.get(composite_key, []):
            if isinstance(sub_schema, dict):
                found.extend(
                    collect_deprecated_fields_in_schema(
                        spec,
                        sub_schema,
                        path_prefix,
                        seen_refs.copy(),
                        enclosing_schema,
                    )
                )

    items = schema.get("items")
    if isinstance(items, dict):
        found.extend(
            collect_deprecated_fields_in_schema(
                spec,
                items,
                path_prefix,
                seen_refs.copy(),
                enclosing_schema,
            )
        )

    return found


def collect_deprecated_parameters(operation: dict) -> list[dict]:
    found: list[dict] = []

    for param in operation.get("parameters", []):
        if not isinstance(param, dict) or not param.get("deprecated"):
            continue

        entry = {
            "field": param.get("name"),
            "property": param.get("name"),
            "schema": None,
            "description": param.get("description"),
            "in": param.get("in"),
        }
        param_schema = param.get("schema")
        if isinstance(param_schema, dict):
            entry["description"] = entry["description"] or param_schema.get(
                "description"
            )
        found.append(entry)

    return found


def collect_deprecated_for_operation(
    spec: dict,
    method: str,
    path: str,
    operation: dict,
) -> list[dict]:
    entries: list[dict] = []

    for param in collect_deprecated_parameters(operation):
        entries.append(
            {
                **param,
                "method": method.upper(),
                "path": path,
                "mintlify_ref": f"{method.upper()} {path}",
                "usage": param.get("in", "parameter"),
            }
        )

    request_body = operation.get("requestBody", {})
    for media_obj in request_body.get("content", {}).values():
        schema = media_obj.get("schema")
        if isinstance(schema, dict):
            for field in collect_deprecated_fields_in_schema(spec, schema):
                entries.append(
                    {
                        **field,
                        "method": method.upper(),
                        "path": path,
                        "mintlify_ref": f"{method.upper()} {path}",
                        "usage": "requestBody",
                    }
                )

    for status_code, response in operation.get("responses", {}).items():
        for media_obj in response.get("content", {}).values():
            schema = media_obj.get("schema")
            if not isinstance(schema, dict):
                continue

            for field in collect_deprecated_fields_in_schema(spec, schema):
                entries.append(
                    {
                        **field,
                        "method": method.upper(),
                        "path": path,
                        "mintlify_ref": f"{method.upper()} {path}",
                        "usage": "response",
                        "status_code": status_code,
                    }
                )

    return entries


def build_deprecated_report(spec: dict, version: str) -> dict:
    all_entries: list[dict] = []

    for path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue

        for method, operation in path_item.items():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue

            all_entries.extend(
                collect_deprecated_for_operation(spec, method, path, operation)
            )

    by_endpoint: OrderedDict[str, dict] = OrderedDict()
    fields_index: OrderedDict[str, dict] = OrderedDict()

    for entry in all_entries:
        mintlify_ref = entry["mintlify_ref"]
        field_name = entry["field"]

        if mintlify_ref not in by_endpoint:
            by_endpoint[mintlify_ref] = {
                "method": entry["method"],
                "path": entry["path"],
                "mintlify_ref": mintlify_ref,
                "deprecated_fields": [],
            }

        field_record = {
            "field": field_name,
            "usage": entry["usage"],
            "description": entry.get("description"),
            "schema": entry.get("schema"),
        }
        if entry.get("status_code") is not None:
            field_record["status_code"] = entry["status_code"]
        if entry.get("in") is not None:
            field_record["in"] = entry["in"]

        by_endpoint[mintlify_ref]["deprecated_fields"].append(field_record)

        field_id = f"{entry.get('schema') or 'inline'}.{field_name}"
        if field_id not in fields_index:
            fields_index[field_id] = {
                "id": field_id,
                "field": field_name,
                "schema": entry.get("schema"),
                "description": entry.get("description"),
                "endpoints": [],
            }

        endpoint_ref = {
            "method": entry["method"],
            "path": entry["path"],
            "mintlify_ref": mintlify_ref,
            "usage": entry["usage"],
        }
        if entry.get("status_code") is not None:
            endpoint_ref["status_code"] = entry["status_code"]
        if entry.get("in") is not None:
            endpoint_ref["in"] = entry["in"]

        existing = fields_index[field_id]["endpoints"]
        if endpoint_ref not in existing:
            existing.append(endpoint_ref)

    for endpoint in by_endpoint.values():
        endpoint["deprecated_fields"] = sorted(
            endpoint["deprecated_fields"],
            key=lambda item: (item["usage"], item["field"]),
        )

    return {
        "info": {
            "version": version,
        },
        "summary": {
            "total_deprecated_fields": len(fields_index),
            "total_deprecated_occurrences": len(all_entries),
            "endpoints_with_deprecated_fields": len(by_endpoint),
        },
        "fields": list(fields_index.values()),
        "by_endpoint": list(by_endpoint.values()),
    }


def strip_deprecated_properties(obj, removed: list[dict], context: dict) -> None:
    if isinstance(obj, dict):
        properties = obj.get("properties")
        if isinstance(properties, dict):
            to_remove = [
                name
                for name, prop in properties.items()
                if isinstance(prop, dict) and prop.get("deprecated")
            ]
            for name in to_remove:
                prop = properties[name]
                removed.append(
                    {
                        "property": name,
                        "path_in_object": (
                            f"{context['path_in_object']}.{name}"
                            if context.get("path_in_object")
                            else name
                        ),
                        "schema": context.get("schema"),
                        "description": prop.get("description")
                        if isinstance(prop, dict)
                        else None,
                        "location": context.get("location", "schema"),
                    }
                )
                del properties[name]

            if isinstance(obj.get("required"), list):
                obj["required"] = [
                    name for name in obj["required"] if name not in to_remove
                ]

            for name, prop in properties.items():
                strip_deprecated_properties(
                    prop,
                    removed,
                    {
                        **context,
                        "path_in_object": (
                            f"{context['path_in_object']}.{name}"
                            if context.get("path_in_object")
                            else name
                        ),
                    },
                )

        parameters = obj.get("parameters")
        if isinstance(parameters, list):
            kept_parameters = []
            for param in parameters:
                if isinstance(param, dict) and param.get("deprecated"):
                    removed.append(
                        {
                            "property": param.get("name"),
                            "path_in_object": param.get("name"),
                            "schema": None,
                            "description": param.get("description"),
                            "location": f"parameter:{param.get('in', 'unknown')}",
                        }
                    )
                    continue

                if isinstance(param, dict) and isinstance(param.get("schema"), dict):
                    strip_deprecated_properties(
                        param["schema"],
                        removed,
                        {
                            **context,
                            "location": f"parameter:{param.get('in', 'unknown')}",
                        },
                    )

                kept_parameters.append(param)

            obj["parameters"] = kept_parameters

        for key, value in obj.items():
            if key in {"properties", "parameters"}:
                continue
            strip_deprecated_properties(value, removed, context)

    elif isinstance(obj, list):
        for item in obj:
            strip_deprecated_properties(item, removed, context)


def strip_deprecated_from_spec(spec: dict) -> tuple[dict, list[dict]]:
    removed: list[dict] = []

    schemas = spec.get("components", {}).get("schemas", {})
    for schema_name, schema in schemas.items():
        strip_deprecated_properties(
            schema,
            removed,
            {
                "schema": schema_name,
                "location": "components.schemas",
            },
        )

    for path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue

        for method, operation in path_item.items():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue

            strip_deprecated_properties(
                operation,
                removed,
                {
                    "location": f"paths.{path}.{method}",
                },
            )

    return spec, removed


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
) -> tuple[dict, list[str], list[str], list[str], list[str], dict]:
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

    deprecated_report = build_deprecated_report(filtered, version)

    filtered, stripped_properties = strip_deprecated_from_spec(filtered)
    deprecated_report["stripped_properties"] = stripped_properties

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

    return (
        filtered,
        kept_paths,
        removed_paths,
        kept_schemas,
        removed_schemas,
        deprecated_report,
    )


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

    filtered, kept_paths, removed_paths, kept_schemas, removed_schemas, deprecated_report = (
        filter_openapi_spec(
            spec=spec,
            patterns=args.pattern,
            version=args.version,
        )
    )

    output_path = Path(args.output)
    deprecated_output_path = output_path.with_name(f"{output_path.stem}-deprecated.json")

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)

    with deprecated_output_path.open("w", encoding="utf-8") as f:
        json.dump(deprecated_report, f, indent=2, ensure_ascii=False)

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

    summary = deprecated_report["summary"]
    print(
        f"\nDeprecated fields: {summary['total_deprecated_fields']} unique field(s) "
        f"across {summary['endpoints_with_deprecated_fields']} endpoint(s)"
    )
    for endpoint in deprecated_report["by_endpoint"]:
        print(f"\n  {endpoint['mintlify_ref']}:")
        for field in endpoint["deprecated_fields"]:
            desc = field.get("description") or ""
            short_desc = (desc[:80] + "…") if len(desc) > 80 else desc
            print(f"    - {field['field']} ({field['usage']}) {short_desc}")

    print(f"\nFiltered spec written to: {output_path}")
    print(f"Deprecated fields report written to: {deprecated_output_path}")


if __name__ == "__main__":
    main()
