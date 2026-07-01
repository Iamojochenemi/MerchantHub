"""
Custom DRF permission classes for MerchantHub.

Permission evaluation order:
    Request → JWTAuthentication → User identified
           → Middleware resolves ``X-Workspace-ID`` → ``request.workspace``
           → Permission class evaluates role-based access
           → View executes (or 403 Forbidden)
"""

from rest_framework import permissions


class IsWorkspaceMember(permissions.BasePermission):
    """Grant access if the authenticated user is a member of the workspace.

    Requires ``WorkspaceMiddleware`` to have populated ``request.workspace``.
    Requires a ``WorkspaceMembership`` model with a ``role`` field.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        workspace = getattr(request, "workspace", None)
        if workspace is None:
            return False
        return request.user.workspacemembership_set.filter(
            workspace=workspace
        ).exists()


class IsWorkspaceOwner(permissions.BasePermission):
    """Grant access only if the user's role in the workspace is ``owner``.

    Expected role values: ``owner`` (level 100).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        workspace = getattr(request, "workspace", None)
        if workspace is None:
            return False
        return request.user.workspacemembership_set.filter(
            workspace=workspace, role="owner"
        ).exists()


class IsManagerOrAbove(permissions.BasePermission):
    """Grant access if the user's role is ``manager`` or ``owner``.

    Expected role values: ``owner`` (level 100), ``manager`` (level 50).
    """

    MANAGER_LEVEL = 50

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        workspace = getattr(request, "workspace", None)
        if workspace is None:
            return False
        membership = request.user.workspacemembership_set.filter(
            workspace=workspace
        ).first()
        if membership is None:
            return False
        # Derive level from the role string.
        # In MVP, role levels are implicit:
        #   owner -> 100, manager -> 50, staff -> 10
        role_level = {"owner": 100, "manager": 50, "staff": 10}.get(
            getattr(membership, "role", ""), 0
        )
        return role_level >= self.MANAGER_LEVEL
