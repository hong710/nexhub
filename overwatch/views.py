import json

from django import forms
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import Category, DataDictionary, DICTIONARY_CATEGORY_CHOICES, Note, Server, Tag


def pretty_json(value):
    if not value:
        return ""
    try:
        return json.dumps(value, indent=2)
    except Exception:
        return ""


def server_list(request: HttpRequest) -> HttpResponse:
    platform_map = {
        d.original_keyword.lower(): d.standardized_value
        for d in DataDictionary.objects.filter(translate_from="product_name", is_active=True)
    }

    total_all_count = Server.objects.count()
    servers = Server.objects.prefetch_related("tags").all()

    query = request.GET.get("q")
    if query:
        platform_matches = list(
            DataDictionary.objects.filter(
                translate_from="product_name", is_active=True, standardized_value__icontains=query
            ).values_list("original_keyword", flat=True)
        )
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
            | Q(tags__name__icontains=query)
        )
        if platform_matches:
            search_filter |= Q(product_name__in=platform_matches)
        if query.isdigit():
            search_filter |= Q(core_count=query) | Q(disk_count=query)
        servers = servers.filter(search_filter)

    tags_filter = request.GET.getlist("tags")
    if tags_filter:
        servers = servers.filter(tags__name__in=tags_filter).distinct()

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

    tag_options = ["__NO_TAG__"] + list(Tag.objects.order_by("name").values_list("name", flat=True))

    for srv in page_obj:
        key = (srv.product_name or "").lower()
        srv.platform_display = platform_map.get(key) or srv.product_name
        srv.tags_list = [t.name for t in srv.tags.all()]

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
        ("category", "Device Type"),
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
        "tag_options": tag_options,
        "tags_filter": tags_filter,
    }

    template = "overwatch/server_list_partial.html" if request.headers.get("HX-Request") else "overwatch/server_list.html"
    return render(request, template, context)


def server_detail(request: HttpRequest, pk: int) -> HttpResponse:
    server = get_object_or_404(Server.objects.prefetch_related("tags"), pk=pk)
    platform_map = {
        d.original_keyword.lower(): d.standardized_value
        for d in DataDictionary.objects.filter(translate_from="product_name", is_active=True)
    }
    key = (server.product_name or "").lower()
    server.platform_display = platform_map.get(key) or server.product_name

    note_form = NoteForm()
    notes = server.notes.order_by("-created_at")

    context = {
        "server": server,
        "note_form": note_form,
        "notes": notes,
        "mem_details_pretty": pretty_json(server.mem_details),
        "disk_details_pretty": pretty_json(server.disk_details),
        "accelerator_pretty": pretty_json(server.accelerator),
        "network_interfaces_pretty": pretty_json(server.network_interfaces),
        "expansion_slots_pretty": pretty_json(server.expansion_slots),
        "user_folders_pretty": pretty_json(server.user_folders),
        "misc_pretty": pretty_json(server.misc),
    }
    return render(request, "overwatch/server_detail.html", context)


# Dictionary views
def dictionary_list(request: HttpRequest) -> HttpResponse:
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
        "category": category_filter or "",
        "translate_from_filter": translate_from_filter or "",
        "translate_from_choices": translate_from_choices,
        "category_choices": DICTIONARY_CATEGORY_CHOICES,
        "page_size": page_size,
        "page_sizes": page_sizes,
        "elided_pages": elided_pages,
        "filtered_count": filtered_count,
        "total_all_count": total_all_count,
    }

    template = (
        "overwatch/dictionary_list_partial.html"
        if request.headers.get("HX-Request")
        else "overwatch/dictionary_list.html"
    )
    return render(request, template, context)


class DictionaryForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        translate_choices = []
        for f in Server._meta.fields:
            if f.name in ["id", "created_at", "updated_at", "updated_by"]:
                continue
            translate_choices.append((f.name, f.verbose_name.title()))
        self.fields["translate_from"].widget.choices = [("", "Select source")] + translate_choices

    class Meta:
        model = DataDictionary
        fields = ["translate_from", "original_keyword", "category", "standardized_value", "description", "is_active"]
        widgets = {
            "translate_from": forms.Select(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "original_keyword": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "category": forms.Select(
                choices=DICTIONARY_CATEGORY_CHOICES,
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"},
            ),
            "standardized_value": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "description": forms.Textarea(
                attrs={"rows": 3, "class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "rounded border-slate-300 text-blue-600"}),
        }


def dictionary_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = DictionaryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("overwatch:dictionary_list")
    else:
        form = DictionaryForm()

    template = (
        "overwatch/dictionary_form_inner.html"
        if request.headers.get("HX-Request")
        else "overwatch/dictionary_form.html"
    )
    return render(
        request,
        template,
        {
            "form": form,
            "form_title": "Add entry",
            "submit_label": "Save",
            "form_action": reverse("overwatch:dictionary_create"),
        },
    )


def dictionary_edit(request: HttpRequest, pk: int) -> HttpResponse:
    entry = get_object_or_404(DataDictionary, pk=pk)
    if request.method == "POST":
        form = DictionaryForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            return redirect("overwatch:dictionary_list")
    else:
        form = DictionaryForm(instance=entry)

    template = (
        "overwatch/dictionary_form_inner.html"
        if request.headers.get("HX-Request")
        else "overwatch/dictionary_form.html"
    )
    return render(
        request,
        template,
        {
            "form": form,
            "form_title": "Edit entry",
            "submit_label": "Update",
            "form_action": reverse("overwatch:dictionary_edit", args=[pk]),
        },
    )


def dictionary_delete(request: HttpRequest, pk: int) -> HttpResponse:
    entry = get_object_or_404(DataDictionary, pk=pk)
    if request.method == "POST":
        entry.delete()
    return redirect("overwatch:dictionary_list")


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "description": forms.Textarea(
                attrs={"rows": 3, "class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["device_type"]
        widgets = {
            "device_type": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
        }


def tag_list(request: HttpRequest) -> HttpResponse:
    tags = Tag.objects.all().order_by("name")
    total_all_count = tags.count()

    query = request.GET.get("q")
    if query:
        tags = tags.filter(Q(name__icontains=query) | Q(description__icontains=query))

    filtered_count = tags.count()

    page_size_input = request.GET.get("page_size")
    try:
        page_size = int(page_size_input) if page_size_input else 25
    except ValueError:
        page_size = 25
    if page_size not in [25, 50, 100, 200]:
        page_size = 25

    page_sizes = [25, 50, 100, 200]

    paginator = Paginator(tags, page_size)
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
    }

    template = "overwatch/tag_list_partial.html" if request.headers.get("HX-Request") else "overwatch/tag_list.html"
    return render(request, template, context)


def tag_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = TagForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("overwatch:tag_list")
    else:
        form = TagForm()

    template = "overwatch/tag_form_inner.html" if request.headers.get("HX-Request") else "overwatch/tag_form.html"
    return render(
        request,
        template,
        {"form": form, "form_title": "Add tag", "submit_label": "Save", "form_action": reverse("overwatch:tag_create")},
    )


def tag_edit(request: HttpRequest, pk: int) -> HttpResponse:
    tag = get_object_or_404(Tag, pk=pk)
    if request.method == "POST":
        form = TagForm(request.POST, instance=tag)
        if form.is_valid():
            form.save()
            return redirect("overwatch:tag_list")
    else:
        form = TagForm(instance=tag)

    template = "overwatch/tag_form_inner.html" if request.headers.get("HX-Request") else "overwatch/tag_form.html"
    return render(
        request,
        template,
        {
            "form": form,
            "form_title": "Edit tag",
            "submit_label": "Update",
            "form_action": reverse("overwatch:tag_edit", args=[pk]),
        },
    )


def tag_delete(request: HttpRequest, pk: int) -> HttpResponse:
    tag = get_object_or_404(Tag, pk=pk)
    if request.method == "POST":
        tag.delete()
    return redirect("overwatch:tag_list")


def category_list(request: HttpRequest) -> HttpResponse:
    categories = Category.objects.all().order_by("device_type")
    total_all_count = categories.count()
    form = CategoryForm()

    query = request.GET.get("q")
    if query:
        categories = categories.filter(device_type__icontains=query)

    filtered_count = categories.count()

    page_size_input = request.GET.get("page_size")
    try:
        page_size = int(page_size_input) if page_size_input else 25
    except ValueError:
        page_size = 25
    if page_size not in [25, 50, 100, 200]:
        page_size = 25

    page_sizes = [25, 50, 100, 200]

    paginator = Paginator(categories, page_size)
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
        "form": form,
    }

    template = (
        "overwatch/category_list_partial.html"
        if request.headers.get("HX-Request")
        else "overwatch/category_list.html"
    )
    return render(request, template, context)


def category_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("overwatch:category_list")
    else:
        form = CategoryForm()

    template = (
        "overwatch/category_form_inner.html"
        if request.headers.get("HX-Request")
        else "overwatch/category_form.html"
    )
    return render(
        request,
        template,
        {
            "form": form,
            "form_title": "Add category",
            "submit_label": "Save",
            "form_action": reverse("overwatch:category_create"),
        },
    )


def category_edit(request: HttpRequest, pk: int) -> HttpResponse:
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            return redirect("overwatch:category_list")
    else:
        form = CategoryForm(instance=category)

    template = (
        "overwatch/category_form_inner.html"
        if request.headers.get("HX-Request")
        else "overwatch/category_form.html"
    )
    return render(
        request,
        template,
        {
            "form": form,
            "form_title": "Edit category",
            "submit_label": "Update",
            "form_action": reverse("overwatch:category_edit", args=[pk]),
        },
    )


def category_delete(request: HttpRequest, pk: int) -> HttpResponse:
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        category.delete()
    return redirect("overwatch:category_list")


class ServerForm(forms.ModelForm):
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.order_by("name").distinct(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "flex flex-col gap-2 text-sm text-slate-700"}),
    )

    class Meta:
        model = Server
        fields = [
            "category",
            "hostname",
            "uuid",
            "ip_address",
            "bmc_ip",
            "nic_mac",
            "bmc_mac",
            "manufacture",
            "product_name",
            "cpu",
            "core_count",
            "sockets",
            "bios_version",
            "bios_release_date",
            "total_mem",
            "disk_count",
            "os",
            "os_version",
            "kernel",
            "building",
            "room",
            "rack",
            "location",
            "status",
            "data_source",
            "assign_to",
            "last_login",
            "pdu_connection",
            "pdu_ip",
            "pdu_port_number",
            "tags",
        ]
        widgets = {
            "category": forms.Select(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "uuid": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "hostname": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "ip_address": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "nic_mac": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "bmc_ip": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "bmc_mac": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "manufacture": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "product_name": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "cpu": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "core_count": forms.NumberInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "sockets": forms.NumberInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "total_mem": forms.NumberInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "disk_count": forms.NumberInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "bios_version": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "bios_release_date": forms.DateInput(
                attrs={"type": "date", "class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "os": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "os_version": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "kernel": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "building": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "room": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "rack": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "location": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "status": forms.Select(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "assign_to": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "last_login": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "data_source": forms.Select(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "pdu_connection": forms.CheckboxInput(attrs={"class": "rounded border-slate-300 text-blue-600"}),
            "pdu_ip": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "pdu_port_number": forms.TextInput(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
        }


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ["content", "priority", "is_public"]
        widgets = {
            "content": forms.Textarea(
                attrs={"rows": 3, "class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "priority": forms.Select(
                attrs={"class": "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"}
            ),
            "is_public": forms.CheckboxInput(attrs={"class": "rounded border-slate-300 text-blue-600"}),
        }


def server_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ServerForm(request.POST)
        if form.is_valid():
            server = form.save()
            return redirect("overwatch:server_detail", pk=server.pk)
    else:
        form = ServerForm()

    return render(
        request,
        "overwatch/server_form.html",
        {"form": form, "form_title": "Add server", "submit_label": "Save", "form_action": reverse("overwatch:server_create")},
    )


def server_edit(request: HttpRequest, pk: int) -> HttpResponse:
    server = get_object_or_404(Server, pk=pk)
    if request.method == "POST":
        form = ServerForm(request.POST, instance=server)
        if form.is_valid():
            form.save()
            return redirect("overwatch:server_detail", pk=pk)
    else:
        form = ServerForm(instance=server)

    return render(
        request,
        "overwatch/server_form.html",
        {"form": form, "form_title": "Edit Server", "submit_label": "Update", "form_action": request.path},
    )


def server_delete(request: HttpRequest, pk: int) -> HttpResponse:
    server = get_object_or_404(Server, pk=pk)
    if request.method == "POST":
        server.delete()
    return redirect("overwatch:server_list")


def server_note_create(request: HttpRequest, pk: int) -> HttpResponse:
    server = get_object_or_404(Server, pk=pk)
    if request.method == "POST":
        form = NoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.server = server
            note.save()
    return redirect("overwatch:server_detail", pk=pk)
