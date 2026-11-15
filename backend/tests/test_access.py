from collections.abc import Callable

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from coop_manager.app import app
from coop_manager.users.access import PUBLIC_PATHS, current_user


def api_routes() -> dict[str, Dependant]:
    """Alle Endpunkte mit vollem Pfad und ihren Dependencies.

    `app.routes` reicht nicht: FastAPI führt eingebundene Router dort nur als einen Eintrag
    (`_IncludedRouter`). `iter_route_contexts` liefert die einzelnen Routen samt Präfix.
    """
    return {
        str(context.path): context.dependant
        for context in iter_route_contexts(app.routes)
        if isinstance(context.original_route, APIRoute)
    }


def dependency_calls(dependant: Dependant) -> set[Callable]:
    """Alle Funktionen, von denen ein Endpunkt abhängt, auch über mehrere Ebenen."""
    calls: set[Callable] = set()
    for dependency in dependant.dependencies:
        if dependency.call is not None:
            calls.add(dependency.call)
        calls |= dependency_calls(dependency)
    return calls


def test_every_route_requires_login_unless_public():
    """Standard ist „Zugriff verweigert“: Ein Endpunkt ohne Prüfung lässt diesen Test scheitern."""
    unprotected = [
        path
        for path, dependant in api_routes().items()
        if path not in PUBLIC_PATHS and current_user not in dependency_calls(dependant)
    ]

    assert unprotected == []


def test_routes_are_found():
    """Schützt den Test oben davor, ins Leere zu prüfen, und PUBLIC_PATHS vor Tippfehlern."""
    paths = set(api_routes())

    assert PUBLIC_PATHS <= paths
    assert {"/api/logout", "/api/me"} <= paths
