"""
Utility functions for the ``workspaces`` app.

Provides helpers related to workspace resolution, membership
queries, and tenant-scoped operations.
"""

from rest_framework.exceptions import ValidationError


def get_active_workspace(request):
    """Resolve the authenticated user's active workspace.

    Looks up the user's active ``WorkspaceMembership`` (``is_active=True``)
    and returns the associated ``Workspace``.  Raises ``ValidationError``
    if no active membership is found.

    This is used instead of ``request.workspace`` because MerchantHub
    does not attach a workspace to the request object.
    """
    membership = (
        request.user.workspace_memberships
        .filter(is_active=True)
        .select_related("workspace")
        .first()
    )
    if membership is None:
        raise ValidationError("No active workspace membership found.")
    return membership.workspace
