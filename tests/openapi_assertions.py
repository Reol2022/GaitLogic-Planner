from typing import Any


HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "options",
    "head",
    "trace",
}


def get_openapi_routes(app: Any) -> set[str]:
    """Return registered public API operations from the OpenAPI contract."""
    paths = app.openapi().get("paths", {})

    return {
        f"{method.upper()} {path}"
        for path, path_item in paths.items()
        for method in path_item
        if method.lower() in HTTP_METHODS
    }


def get_openapi_methods(app: Any, path: str) -> set[str]:
    """Return HTTP methods exposed by one public OpenAPI path."""
    path_item = app.openapi().get("paths", {}).get(path, {})

    return {
        method.upper()
        for method in path_item
        if method.lower() in HTTP_METHODS
    }
