from django import forms
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import DataDictionary, Server, DICTIONARY_CATEGORY_CHOICES


def server_list(request: HttpRequest) -> HttpResponse:
    """
    Simple server list with search, filter, sort, and pagination.
    HTMX can update the table body without reloading the whole page.
    """

    platform_map = {
        d.original_keyword.lower(): d.standardized_value
        for d in DataDictionary.objects.filter(translate_from="product_name", is_active=True)
    }

    total_all_count = Server.objects.count()
    servers = Server.objects.all()

    # Search across many visible fields
    query = request.GET.get("q")
    if query:
        q_digit = query.isdigit()
        platform_matches = [
            d.original_keyword
            for d in DataDictionary.objects.filter(
                translate_from="product_name", is_active=True, standardized_value__icontains=query
            )
        ]
        search_filter = (
            Q(hostname__icontains=query)
            | Q(ip_address__icontains=query)
            | Q(bmc_ip__icontains=query)
            | Q(os__icontains=query)
            | Q(os_version__icontains=query)
            | Q(kernel__icontains=query)
            | Q(cpu__icontains=query)
            | Q(manufacture__icontains=query)
            | Q(product_name__icontains=query)
            | Q(bios_version__icontains=query)
            | Q(room__icontains=query)
            | Q(rack__icontains=query)
            | Q(location__icontains=query)
            | Q(data_source__icontains=query)
            | Q(tags__icontains=query)
        )
        if platform_matches:
            search_filter |= Q(product_name__in=platform_matches)
        if q_digit:
            search_filter |= Q(core_count=query) | Q(disk_count=query)
        servers = servers.filter(search_filter)

    # Default ordering for consistency
    servers = servers.order_by("hostname")

    page_size_input = request.GET.get("page_size")
    try:
        requested_page_size = int(page_size_input) if page_size_input else 25
    except ValueError:
        requested_page_size = 25
    if requested_page_size not in [25, 50, 100, 200]:
        requested_page_size = 25

    page_sizes = [25, 50, 100, 200]

    filtered_count = servers.count()

    # If the filtered result set is smaller than the requested page size,
    # auto-shrink the page size so pagination collapses to a single page.
    page_size_disabled = False
    effective_page_size = requested_page_size
    if filtered_count < requested_page_size:
        effective_page_size = max(filtered_count, 1)
        page_size_disabled = True

    paginator = Paginator(servers, effective_page_size)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    elided_pages = paginator.get_elided_page_range(number=page_obj.number, on_each_side=1, on_ends=1)
    page_offset = page_obj.start_index() - 1 if filtered_count else 0

    # Attach computed platform and parsed tags to each server in the current page
    for srv in page_obj:
        key = (srv.product_name or "").lower()
        srv.platform_display = platform_map.get(key) or srv.product_name
        srv.tags_list = [t.strip() for t in (srv.tags or "").split(",") if t.strip()]

    table_headers = [
        ("ip_address", "IP"),
        ("bmc_ip", "BMC IP"),
        ("hostname", "Hostname"),
        ("os", "OS"),
        ("os_version", "OS Version"),
        ("kernel", "Kernel"),
        ("cpu", "CPU"),
        ("core_count", "Core Count"),
        ("manufacture", "Manufacture"),
        ("product_name", "Product Name"),
        ("platform", "Platform"),
        ("bios_version", "BIOS Version"),
        ("room", "Room"),
        ("rack", "Rack"),
        ("location", "Location"),
        ("updated_at", "Updated"),
        ("disk_count", "Disk Count"),
        ("data_source", "Data Source"),
        ("tags", "Tags"),
    ]

    col_toggles = [
        ("manufacture", "Manufacture"),
        ("bios_version", "BIOS Version"),
        ("product_name", "Product Name"),
        ("disk_count", "Disk count"),
        ("data_source", "Data source"),
        ("tags", "Tags"),
    ]

    context = {
        "page_obj": page_obj,
        "query": query or "",
        "table_headers": table_headers,
        "page_size": effective_page_size,
        "page_sizes": page_sizes,
        "elided_pages": elided_pages,
        "col_toggles": col_toggles,
        "filtered_count": filtered_count,
        "total_all_count": total_all_count,
        "page_size_disabled": page_size_disabled,
        "page_offset": page_offset,
    }

    template = "overwatch/server_list_partial.html" if request.headers.get("HX-Request") else "overwatch/server_list.html"
    return render(request, template, context)


def server_detail(request: HttpRequest, pk: int) -> HttpResponse:
    server = get_object_or_404(Server, pk=pk)
    return render(request, "overwatch/server_detail.html", {"server": server})


def dictionary_list(request: HttpRequest) -> HttpResponse:
    """List and search dictionary terms."""

    items = DataDictionary.objects.all().order_by("original_keyword")
    total_all_count = items.count()

    query = request.GET.get("q")
    if query:
        items = items.filter(
            Q(original_keyword__icontains=query)
            | Q(translate_from__icontains=query)
            | Q(standardized_value__icontains=query)
            | Q(category__icontains=query)
            | Q(description__icontains=query)
        )

    category_filter = request.GET.get("category")
    if category_filter:
        items = items.filter(category=category_filter)

    active_filter = request.GET.get("active")
    if active_filter in ["true", "false"]:
        items = items.filter(is_active=(active_filter == "true"))

    # Translate-from filter (use Server fields as choices)
    translate_from_choices = []
    for f in Server._meta.fields:
        if f.name in ["id", "created_at", "updated_at", "updated_by"]:
            continue
        translate_from_choices.append((f.name, f.verbose_name.title()))

    translate_from_filter = request.GET.get("translate_from")
    if translate_from_filter:
        items = items.filter(translate_from=translate_from_filter)

    filtered_count = items.count()

    page_size_input = request.GET.get("page_size")
    try:
        page_size = int(page_size_input) if page_size_input else 25
    except ValueError:
        page_size = 25
    if page_size not in [25, 50, 100, 200]:
        page_size = 25

    page_sizes = [25, 50, 100, 200]

    paginator = Paginator(items, page_size)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    elided_pages = paginator.get_elided_page_range(number=page_obj.number, on_each_side=1, on_ends=1)

    context = {
        "page_obj": page_obj,
        "query": query or "",
        "page_size": page_size,
        "page_sizes": page_sizes,
        "elided_pages": elided_pages,
        "filtered_count": filtered_count,
        "total_all_count": total_all_count,
        "category_filter": category_filter or "",
        "active_filter": active_filter or "",
        "category_choices": DICTIONARY_CATEGORY_CHOICES,
        "translate_from_filter": translate_from_filter or "",
        "translate_from_choices": translate_from_choices,
    }

    template = (
        "overwatch/dictionary_list_partial.html"
        if request.headers.get("HX-Request")
        else "overwatch/dictionary_list.html"
    )
    return render(request, template, context)


class DataDictionaryForm(forms.ModelForm):
    translate_from = forms.ChoiceField(required=True)

    class Meta:
        model = DataDictionary
        fields = ["translate_from", "original_keyword", "category", "standardized_value", "description", "is_active"]
        widgets = {
            "original_keyword": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "category": forms.Select(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "standardized_value": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm",
                }
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "rounded border-slate-300 text-blue-600"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Build choices from Server model fields (exclude id and audit)
        field_choices = []
        for f in Server._meta.fields:
            if f.name in ["id", "created_at", "updated_at", "updated_by"]:
                continue
            label = f.verbose_name.title()
            field_choices.append((f.name, label))
        self.fields["translate_from"].choices = field_choices
        self.fields["translate_from"].widget.attrs.update(
            {"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
        )
        self.fields["translate_from"].label = "Translate From (Server column)"
        self.fields["category"].label = "Translate To"


def dictionary_create(request: HttpRequest) -> HttpResponse:
    """Simple create form for dictionary entries."""

    if request.method == "POST":
        form = DataDictionaryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("overwatch:dictionary_list")
    else:
        form = DataDictionaryForm()

    template = (
        "overwatch/dictionary_form_inner.html" if request.headers.get("HX-Request") else "overwatch/dictionary_form.html"
    )
    return render(
        request,
        template,
        {
            "form": form,
            "form_title": "Add dictionary entry",
            "submit_label": "Save",
            "form_action": reverse("overwatch:dictionary_create"),
        },
    )


def dictionary_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """Edit an existing dictionary entry."""

    entry = get_object_or_404(DataDictionary, pk=pk)
    if request.method == "POST":
        form = DataDictionaryForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            return redirect("overwatch:dictionary_list")
    else:
        form = DataDictionaryForm(instance=entry)

    template = (
        "overwatch/dictionary_form_inner.html" if request.headers.get("HX-Request") else "overwatch/dictionary_form.html"
    )
    return render(
        request,
        template,
        {
            "form": form,
            "form_title": "Edit dictionary entry",
            "submit_label": "Update",
            "form_action": reverse("overwatch:dictionary_edit", args=[pk]),
        },
    )


def dictionary_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete a dictionary entry after confirmation."""

    entry = get_object_or_404(DataDictionary, pk=pk)
    if request.method == "POST":
        entry.delete()
        return redirect("overwatch:dictionary_list")
    return redirect("overwatch:dictionary_list")
