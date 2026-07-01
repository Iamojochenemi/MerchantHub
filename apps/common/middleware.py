"""
Middleware for workspace resolution from the ``X-Workspace-ID`` header.

Flow
----
1. Read ``HTTP_X_WORKSPACE_ID`` from the request headers.
2. Resolve it to a ``Workspace`` instance.
3. Verify the authenticated user has an active membership.
4. Attach ``request.workspace``.

If the header is missing and the view requires workspace scoping,
the permission class (``IsWorkspaceMember``) will return 403.
"""

from django.utils.deprecation import MiddlewareMixin
from rest_framework.exceptions import PermissionDenied


class WorkspaceMiddleware(MiddlewareMixin):
    """Extract ``X-Workspace-ID`` and attach ``request.workspace``."""

    def process_request(self, request):
        workspace_id = request.META.get("HTTP_X_WORKSPACE_ID")
        if not workspace_id:
            # The view's permission classes will handle denial.
            request.workspace = None
            return

        from apps.workspaces.models import Workspace

        try:
            workspace = Workspace.objects.get(id=workspace_id)
        except (Workspace.DoesNotExist, ValueError):
            request.workspace = None
            return

        # If the user is authenticated, verify membership.
        if request.user.is_authenticated:
            from apps.workspaces.models import WorkspaceMembership

            if not WorkspaceMembership.objects.filter(
                workspace=workspace, user=request.user
            ).exists():
                raise PermissionDenied("You are not a member of this workspace.")

        request.workspace = workspace
