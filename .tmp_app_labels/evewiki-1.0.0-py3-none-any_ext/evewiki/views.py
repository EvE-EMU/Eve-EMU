"""Views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.shortcuts import redirect, render

from allianceauth.authentication.models import UserProfile

from .forms import PageForm
from .models.logs import Log
from .models.page_versions import PageVersion
from .models.pages import Page
from .models.settings import Setting


@login_required
@permission_required("evewiki.basic_access")
def index(request: WSGIRequest, unknown_path: str = "/"):
    """Render index view."""

    try:

        settings = Setting.get_settings()

    except Exception as e:
        print(f"setup required: {e}")
        return render(request, "evewiki/error.html")

    is_editor = False
    if request.user.has_perm("evewiki.editor_access"):
        is_editor = True

    # Control light/dark mode on md editor
    dark_mode = False
    themes_to_use_dark_mode = ["allianceauth.theme.darkly.auth_hooks.DarklyThemeHook"]
    user = UserProfile.objects.filter(user=request.user).first()
    if user.theme in themes_to_use_dark_mode:
        dark_mode = True

    # Tree is too complex to call directly froma template
    tree = Page.tree(user=request.user)

    # "Unknown" i.e. has not bee picked up by urls.py
    page = Page.get_by_path(path=unknown_path, user=request.user)

    # Load the first page by default if nothing else can be found
    # If there is no first-page, template will load a help page.
    if page is None:
        page = Page.objects.order_by("id").first()

    # Content save
    new_content = request.POST.get("content")
    if new_content is not None:
        try:
            # Save the content
            page.content = request.POST.get("content")
            page.save()
            # Record a version of the content
            page_version = PageVersion(
                page=page,
                user=user,
                content=page.content,
            )
            page_version.save()
            # Log a thing happened
            Log(user=user, action=f"Page content modified: {page.title}").save()
            messages.success(request, f"Page '{page.title}' saved")
            return redirect(f"/evewiki/{page.path}")
        except Page.DoesNotExist:
            pass

    context = {
        "context-title": "context-not-title",
        "tree": tree,
        "page": page,
        "dark_mode": dark_mode,
        "settings": settings,
        "is_editor": is_editor,
    }
    return render(request, "evewiki/index.html", context)


@login_required
@permission_required("evewiki.basic_access")
def page(request: WSGIRequest) -> HttpResponse:

    try:
        if (
            not request.user.has_perm("evewiki.editor_access")
            and not request.user.profile.state.name == "Admin"
        ):
            return redirect("/evewiki")

        user = UserProfile.objects.filter(user=request.user).first()
        page = None
        page_id = request.GET.get("id") or request.POST.get("id")
        if page_id is not None:
            try:
                page = Page.objects.get(id=page_id)
            except Page.DoesNotExist:
                page = None

        if request.method == "POST":
            form = PageForm(request.POST, instance=page)
            if form.is_valid():
                saved_page = form.save()
                Log(user=user, action=f"Page Created: {saved_page.title}").save()
                messages.success(request, f"Page '{saved_page.title}' saved")
                return redirect(f"/evewiki/{saved_page.path}")
        else:
            form = PageForm(instance=page)

        page_versions = PageVersion.objects.filter(page=page).order_by("-created").all()

        context = {
            "Page": "Page",
            "page": page,
            "form": form,
            "versions": page_versions,
        }
        return render(request, "evewiki/page.html", context)
    except Exception as e:
        print(f"setup required: {e}")
        return render(request, "evewiki/error.html")


@login_required
@permission_required("evewiki.basic_access")
def page_delete(request: WSGIRequest) -> HttpResponse:

    try:
        if (
            not request.user.has_perm("evewiki.editor_access")
            and not request.user.profile.state.name == "Admin"
        ):
            return redirect("/evewiki")

        user = UserProfile.objects.filter(user=request.user).first()
        page = None
        page_id = request.GET.get("id")
        confirm_delete = request.GET.get("confirm_delete")
        if page_id is not None:
            try:
                page = Page.objects.get(id=page_id)
            except Page.DoesNotExist:
                page = None

        # Check if page has children
        children = Page.objects.filter(parent_id=page_id).all()
        if len(children) > 0:
            messages.error(request, "You cannot delete a page that has children.")

        # Confirm the confirmation that this user definitely wants to delete
        if confirm_delete == "true":
            messages.success(request, f"Page '{page.title}' deleted")
            page.delete()
            # Pages can be deleted, links can be broken, versions orphaned.
            # But the log is immutable
            Log(user=user, action=f"Page Deleted: {page.title}").save()
            return redirect("/evewiki/index")

        context = {"Delete Page": "Delete Page", "page": page, "children": children}
        return render(request, "evewiki/page_delete.html", context)
    except Exception as e:
        print(f"setup required: {e}")
        return render(request, "evewiki/error.html")


def public(request: WSGIRequest, public_path: str = "/") -> HttpResponse:

    try:
        page = Page.get_by_path(path=public_path, user=request.user)

        if page is None:
            return redirect("/evewiki")

        context = {"context-title": "context-not-title", "page": page}
        return render(request, "evewiki/public.html", context)
    except Exception as e:
        print(f"setup required: {e}")
        return render(request, "evewiki/error.html")
