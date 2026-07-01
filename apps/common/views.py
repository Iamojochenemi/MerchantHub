from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet


class WorkspaceScopedViewSet(ModelViewSet):
    """ModelViewSet that automatically filters querysets to the
    active workspace (``request.workspace``).

    Subclasses **must** define a ``queryset`` or ``get_queryset()``.
    The queryset is filtered to ``request.workspace`` before any
    list / retrieve / update / destroy operation.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        workspace = getattr(self.request, "workspace", None)
        if workspace is not None:
            return qs.filter(workspace=workspace)
        return qs

    def perform_create(self, serializer):
        workspace = getattr(self.request, "workspace", None)
        if workspace is not None:
            serializer.save(workspace=workspace)
        else:
            serializer.save()


class WorkspaceScopedReadOnlyViewSet(ReadOnlyModelViewSet):
    """ReadOnlyModelViewSet that automatically filters querysets to the
    active workspace.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        workspace = getattr(self.request, "workspace", None)
        if workspace is not None:
            return qs.filter(workspace=workspace)
        return qs
