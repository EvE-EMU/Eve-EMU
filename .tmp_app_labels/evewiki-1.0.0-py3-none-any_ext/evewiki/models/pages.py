import re
from html import escape

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models

from allianceauth.authentication.models import State


class General(models.Model):
    """A meta model for app permissions."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("basic_access", "Can access this app"),
            ("editor_access", "Can edit this app"),
        )


class Page(models.Model):
    """
    Pages in a hierarchy, identifiable by slugs with a light touch of folder sorting.
    """

    title = models.CharField(
        max_length=255,
        null=False,
        help_text="Required: Displayed above content and in menu",
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
        help_text="Required: Organise page hierarchy",
    )

    slug = models.CharField(
        max_length=255, help_text="Required: Indentifier for path and links"
    )

    priority = models.IntegerField(
        default=10, help_text="Required: Sort order for pages on the same path"
    )

    states = models.ManyToManyField(
        State,
        default=None,
        blank=True,
        related_name="+",
        verbose_name=("states"),
        help_text="Optional: Restrict Page to selected States",
    )

    groups = models.ManyToManyField(
        Group,
        default=None,
        blank=True,
        related_name="+",
        verbose_name=("groups"),
        help_text="Optional: Restrict Page to selected Groups",
    )

    is_public = models.BooleanField(
        default=False,
        help_text="Optional: Make page publicly accessible via /evewiki/<strong style='text-decoration:underline'>public</strong>/[path]/[slug]",
    )

    content = models.TextField(default="", blank=True, null=True)

    def __str__(self):
        return self.title

    def clean(self):

        # Force slugs to be alphanumber lowercase with dashes
        self.slug = self.slug.lower().replace(" ", "-")
        self.slug = re.sub(r"[^a-z0-9\-]", "", self.slug)

        # Check slug is unique for this path
        # Prepare the queryset for siblings (excluding self if updating)
        siblings_qs = Page.objects.filter(parent=self.parent)
        if self.pk is not None:
            siblings_qs = siblings_qs.exclude(pk=self.pk)

        sibling_slugs = list(siblings_qs.values_list("slug", flat=True))
        if self.slug in sibling_slugs:
            raise ValidationError(
                f'A slug with "{self.slug}" already exists ar this path'
            )

        # Check circular reference to self
        if self.parent and self.pk and self.parent.pk == self.pk:
            raise ValidationError("A page cannot be its own parent.")

        # Restrict /public slug
        if not self.parent and self.slug == "public":
            raise ValidationError("'public' is a reserved slug at this level.")

    @property
    def path(self):
        segments = []
        node = self
        while node is not None:
            segments.append(node.slug)
            node = node.parent
        return "/".join(reversed(segments))

    @property
    def summary(self):
        """
        Generates a summary of headers from Markdown text as a nested HTML list of links.
        """
        header_pattern = re.compile(r"^(#{1,6})\s+(.*)", re.MULTILINE)
        headers = []

        for match in header_pattern.finditer(self.content):
            hashes, title = match.groups()
            level = len(hashes)
            anchor = re.sub(r"[^\w\s-]", "", title).strip().lower()
            anchor = re.sub(r"\s+", "-", anchor)
            headers.append((level, title, anchor))

        # Build nested HTML list
        html = []
        prev_level = 0
        for level, title, anchor in headers:
            while prev_level < level:
                html.append("<ul>")
                prev_level += 1
            while prev_level > level:
                html.append("</ul>")
                prev_level -= 1
            html.append(f'<li><a href="#{escape(anchor)}">{escape(title)}</a></li>')
        while prev_level > 0:
            html.append("</ul>")
            prev_level -= 1

        return "\n".join(html)

    @classmethod
    def list(cls, pages=None, parent=None, level=0):
        """
        Returns a flat list of pages with titles indented by hierarchy level.
        Returns: list of tuple
        """
        if pages is None:
            pages = list(cls.objects.all().select_related("parent"))

        flat = []
        children = [p for p in pages if p.parent_id == (parent.id if parent else None)]
        children.sort(key=lambda p: p.priority)

        for child in children:
            indent = "\u2003" * level
            display = f"{indent}{child.title} [/{child.path}]"
            flat.append((child.id, display))
            flat.extend(cls.list(pages, child, level + 1))

        if parent is None and level == 0:
            flat.insert(0, ("", "/"))

        return flat

    @classmethod
    def tree(cls, user=None, pages=None, parent=None, depth=0):
        """
        Recursively builds a tree of pages as nested dicts,
        ordered by priority, with 'path' property.
        Returns: List[Dict]
        """
        if pages is None:
            pages = list(cls.objects.all().select_related("parent"))

        tree = []
        children = [p for p in pages if p.parent_id == (parent.id if parent else None)]
        children.sort(key=lambda p: p.priority)

        for child in children:
            node = {
                "id": child.id,
                "title": child.title,
                "slug": child.slug,
                "priority": child.priority,
                "path": getattr(child, "path", None),
                "depth": depth,
                "children": cls.tree(user, pages, child, depth=depth + 1),
            }
            if child.user_access(user=user):
                tree.append(node)
        return tree

    @classmethod
    def get_by_path(cls, path: str, user):
        """
        Find an id for a given path
        Returns: Page id or None
        """
        path = path.split("/")
        parent = None
        page = None
        for slug in path:
            try:
                page = cls.objects.filter(slug=slug, parent=parent).first()
            except cls.DoesNotExist:
                return None
            parent = page

        if page and page.is_public:
            return page

        if page and not page.user_access(user=user):
            return None

        return page if page else None

    def user_access(self, user):

        # Admin has full access
        if user.profile.state.name == "Admin":
            return True

        # Editor has full access
        if user.has_perm("evewiki.editor_access"):
            return True

        access = False

        # If no groups or states assigned then yes
        groups_empty = not self.groups.exists()
        states_empty = not self.states.exists()
        if groups_empty and states_empty:
            access = True

        # If any of the user's groups are allowed access
        user_has_group = False
        if any(
            group in self.groups.all()
            for group in user.groups.values_list("name", flat=True)
        ):
            access = True
            user_has_group = True

        # If the user's states is in the states list
        user_has_state = False
        if self.states.filter(name=user.profile.state.name).exists():
            access = True
            user_has_state = True

        # If Page has both User needs both
        if not groups_empty and not states_empty:
            access = False
            if user_has_group and user_has_state:
                access = True

        return access
