import json
from dataclasses import dataclass
from io import StringIO
from typing import Any

from django import forms
from django.core.paginator import Paginator
from django.core.management import call_command
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Q, QuerySet
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Category, DataDictionary, DICTIONARY_CATEGORY_CHOICES, IPAM, IPAM_STATUS_CHOICES, Note, Server, Subnet, Tag
from .serializers import CategorySerializer, ServerSerializer, SubnetSerializer, TagSerializer


# =============================================================================
# CONSTANTS - DRY CSS classes for form widgets
# =============================================================================
FORM_INPUT_CLASS = "w-full rounded-lg border-slate-300 focus:border-blue-600 focus:ring-blue-600 text-sm"
FORM_TEXTAREA_CLASS = FORM_INPUT_CLASS
FORM_SELECT_CLASS = FORM_INPUT_CLASS
FORM_CHECKBOX_CLASS = "rounded border-slate-300 text-blue-600"

PAGE_SIZES = [25, 50, 100, 200]
DEFAULT_PAGE_SIZE = 25


# =============================================================================
# HELPER FUNCTIONS - DRY utilities
# =============================================================================
def pretty_json(value):
    if not value:
        return ""
    try:
        return json.dumps(value, indent=2)
    except Exception:
        return ""


def get_page_size(request: HttpRequest) -> int:
    """Extract and validate page size from request."""
    page_size_input = request.GET.get("page_size")
    try:
        page_size = int(page_size_input) if page_size_input else DEFAULT_PAGE_SIZE
    except ValueError:
        page_size = DEFAULT_PAGE_SIZE
    if page_size not in PAGE_SIZES:
        page_size = DEFAULT_PAGE_SIZE
    return page_size


def paginate_queryset(queryset: QuerySet, request: HttpRequest) -> dict[str, Any]:
    """
    Paginate a queryset and return context dict with pagination info.
    Returns: dict with page_obj, page_size, page_sizes, elided_pages
    """
    page_size = get_page_size(request)
    paginator = Paginator(queryset, page_size)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    elided_pages = paginator.get_elided_page_range(number=page_obj.number, on_each_side=1, on_ends=1)

    return {
        "page_obj": page_obj,
        "page_size": page_size,
        "page_sizes": PAGE_SIZES,
        "elided_pages": elided_pages,
    }


def get_htmx_template(request: HttpRequest, partial_template: str, full_template: str) -> str:
    """Return partial template for HTMX requests, full template otherwise."""
    return partial_template if request.headers.get("HX-Request") else full_template


@dataclass
class CRUDConfig:
    """Configuration for generic CRUD operations."""
    model: type
    form_class: type
    list_url_name: str
    create_url_name: str
    edit_url_name: str
    delete_url_name: str
    template_prefix: str  # e.g., "overwatch/tag" -> will use tag_list.html, tag_form.html, etc.
    entity_name: str  # e.g., "tag", "entry", "category"


def generic_create_view(
    request: HttpRequest,
    config: CRUDConfig,
    extra_context: dict[str, Any] | None = None,
) -> HttpResponse:
    """Generic create view for simple CRUD entities."""
    if request.method == "POST":
        form = config.form_class(request.POST)
        if form.is_valid():
            form.save()
            # For HTMX requests, return a response that triggers page refresh
            if request.headers.get("HX-Request"):
                response = HttpResponse()
                response["HX-Redirect"] = reverse(config.list_url_name)
                return response
            return redirect(config.list_url_name)
    else:
        form = config.form_class()

    template = get_htmx_template(
        request,
        f"{config.template_prefix}_form_inner.html",
        f"{config.template_prefix}_form.html",
    )
    context = {
        "form": form,
        "form_title": f"Add {config.entity_name}",
        "submit_label": "Save",
        "form_action": reverse(config.create_url_name),
    }
    if extra_context:
        context.update(extra_context)
    return render(request, template, context)


def generic_edit_view(
    request: HttpRequest,
    pk: int,
    config: CRUDConfig,
    extra_context: dict[str, Any] | None = None,
) -> HttpResponse:
    """Generic edit view for simple CRUD entities."""
    instance = get_object_or_404(config.model, pk=pk)
    if request.method == "POST":
        form = config.form_class(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            # For HTMX requests, return a response that triggers page refresh
            if request.headers.get("HX-Request"):
                response = HttpResponse()
                response["HX-Redirect"] = reverse(config.list_url_name)
                return response
            return redirect(config.list_url_name)
    else:
        form = config.form_class(instance=instance)

    template = get_htmx_template(
        request,
        f"{config.template_prefix}_form_inner.html",
        f"{config.template_prefix}_form.html",
    )
    context = {
        "form": form,
        "form_title": f"Edit {config.entity_name}",
        "submit_label": "Update",
        "form_action": reverse(config.edit_url_name, args=[pk]),
        "object": instance,
    }
    if extra_context:
        context.update(extra_context)
    return render(request, template, context)


def generic_delete_view(request: HttpRequest, pk: int, config: CRUDConfig) -> HttpResponse:
    """Generic delete view for simple CRUD entities."""
    instance = get_object_or_404(config.model, pk=pk)
    if request.method == "POST":
        instance.delete()
    return redirect(config.list_url_name)


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
    total_notes_count = notes.count()

    context = {
        "server": server,
        "note_form": note_form,
        "notes": notes,
        "total_notes_count": total_notes_count,
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
    pagination = paginate_queryset(items, request)

    context = {
        **pagination,
        "query": query or "",
        "category": category_filter or "",
        "translate_from_filter": translate_from_filter or "",
        "translate_from_choices": translate_from_choices,
        "category_choices": DICTIONARY_CATEGORY_CHOICES,
        "filtered_count": filtered_count,
        "total_all_count": total_all_count,
    }

    template = get_htmx_template(request, "overwatch/dictionary_list_partial.html", "overwatch/dictionary_list.html")
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

    def clean(self):
        cleaned_data = super().clean()
        original_keyword = cleaned_data.get("original_keyword")
        category = cleaned_data.get("category")
        
        if original_keyword and category:
            # Check for duplicate (excluding current instance when editing)
            qs = DataDictionary.objects.filter(original_keyword__iexact=original_keyword, category=category)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    f"A dictionary entry with keyword '{original_keyword}' already exists for category '{category}'."
                )
        return cleaned_data

    class Meta:
        model = DataDictionary
        fields = ["translate_from", "original_keyword", "category", "standardized_value", "description", "is_active"]
        widgets = {
            "translate_from": forms.Select(attrs={"class": FORM_SELECT_CLASS}),
            "original_keyword": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
            "category": forms.Select(choices=DICTIONARY_CATEGORY_CHOICES, attrs={"class": FORM_SELECT_CLASS}),
            "standardized_value": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
            "description": forms.Textarea(attrs={"rows": 3, "class": FORM_TEXTAREA_CLASS}),
            "is_active": forms.CheckboxInput(attrs={"class": FORM_CHECKBOX_CLASS}),
        }


# CRUD Configuration for Dictionary
DICTIONARY_CONFIG = CRUDConfig(
    model=DataDictionary,
    form_class=DictionaryForm,
    list_url_name="overwatch:dictionary_list",
    create_url_name="overwatch:dictionary_create",
    edit_url_name="overwatch:dictionary_edit",
    delete_url_name="overwatch:dictionary_delete",
    template_prefix="overwatch/dictionary",
    entity_name="entry",
)


def dictionary_create(request: HttpRequest) -> HttpResponse:
    return generic_create_view(request, DICTIONARY_CONFIG)


def dictionary_edit(request: HttpRequest, pk: int) -> HttpResponse:
    return generic_edit_view(request, pk, DICTIONARY_CONFIG)


def dictionary_delete(request: HttpRequest, pk: int) -> HttpResponse:
    return generic_delete_view(request, pk, DICTIONARY_CONFIG)


@require_POST
def dictionary_apply_translations(request: HttpRequest) -> HttpResponse:
    if not request.user.is_staff:
        return HttpResponse("Error: Forbidden - Staff access required", status=403, content_type="text/plain")

    dry_run = request.POST.get("dry_run") == "true"
    buffer = StringIO()
    try:
        call_command("apply_translations", dry_run=dry_run, stdout=buffer)
        output = buffer.getvalue()
    except Exception as e:
        output = f"Error: {str(e)}"
    
    return HttpResponse(output, content_type="text/plain; charset=utf-8")


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
            "description": forms.Textarea(attrs={"rows": 3, "class": FORM_TEXTAREA_CLASS}),
        }

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if name:
            # Check for duplicate (case-insensitive, excluding current instance when editing)
            qs = Tag.objects.filter(name__iexact=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"A tag with the name '{name}' already exists.")
        return name


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["device_type"]
        widgets = {
            "device_type": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
        }

    def clean_device_type(self):
        device_type = self.cleaned_data.get("device_type")
        if device_type:
            # Check for duplicate (case-insensitive, excluding current instance when editing)
            qs = Category.objects.filter(device_type__iexact=device_type)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"A category with the device type '{device_type}' already exists.")
        return device_type


# CRUD Configurations
TAG_CONFIG = CRUDConfig(
    model=Tag,
    form_class=TagForm,
    list_url_name="overwatch:tag_list",
    create_url_name="overwatch:tag_create",
    edit_url_name="overwatch:tag_edit",
    delete_url_name="overwatch:tag_delete",
    template_prefix="overwatch/tag",
    entity_name="tag",
)

CATEGORY_CONFIG = CRUDConfig(
    model=Category,
    form_class=CategoryForm,
    list_url_name="overwatch:category_list",
    create_url_name="overwatch:category_create",
    edit_url_name="overwatch:category_edit",
    delete_url_name="overwatch:category_delete",
    template_prefix="overwatch/category",
    entity_name="category",
)


class SubnetForm(forms.ModelForm):
    static_pools_input = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label="Static IP Pools",
    )

    class Meta:
        model = Subnet
        fields = ["name", "network", "vlan_id", "gateway", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": FORM_INPUT_CLASS, "placeholder": "e.g. Production LAN"}),
            "network": forms.TextInput(attrs={"class": FORM_INPUT_CLASS, "placeholder": "e.g. 192.168.1.0/24"}),
            "vlan_id": forms.NumberInput(attrs={"class": FORM_INPUT_CLASS, "placeholder": "e.g. 100", "min": "1", "max": "4094"}),
            "gateway": forms.TextInput(attrs={"class": FORM_INPUT_CLASS, "placeholder": "e.g. 192.168.1.1"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": FORM_TEXTAREA_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Prepare initial pools as JSON for the template
        self.initial_pools_json = "[]"
        if self.instance and self.instance.pk and self.instance.static_ip_pools:
            import json
            pools_data = []
            for pool_str in self.instance.static_ip_pools:
                if '-' in pool_str:
                    start, end = pool_str.split('-')
                    pools_data.append({"start": start.strip(), "end": end.strip()})
            self.initial_pools_json = json.dumps(pools_data)

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if name:
            qs = Subnet.objects.filter(name__iexact=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"A subnet with the name '{name}' already exists.")
        return name

    def clean_network(self):
        """Validate CIDR network notation."""
        import ipaddress as ip_lib
        network = self.cleaned_data.get("network", "")
        if network:
            try:
                ip_lib.ip_network(network, strict=False)
            except ValueError:
                raise forms.ValidationError("Invalid network format. Use CIDR notation, e.g. 192.168.1.0/24")
        return network

    def clean_gateway(self):
        """Validate gateway IP address."""
        gateway = self.cleaned_data.get("gateway", "")
        if gateway and not validate_ip_address(gateway):
            raise forms.ValidationError("Invalid gateway IP address format.")
        return gateway

    def clean_vlan_id(self):
        """Validate VLAN ID range."""
        vlan_id = self.cleaned_data.get("vlan_id")
        if vlan_id is not None:
            if vlan_id < 1 or vlan_id > 4094:
                raise forms.ValidationError("VLAN ID must be between 1 and 4094.")
        return vlan_id

    def clean_static_pools_input(self):
        """Validate and parse static IP pools from JSON data."""
        import ipaddress as ip_lib
        import json
        
        # Get the JSON data from the hidden field
        static_pools_data = self.data.get("static_pools_data", "[]")
        
        try:
            pools_list = json.loads(static_pools_data)
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid pool data format.")
        
        if not pools_list:
            return []
        
        pools = []
        for pool in pools_list:
            start_ip = pool.get("start", "").strip()
            end_ip = pool.get("end", "").strip()
            
            if not start_ip or not end_ip:
                continue
            
            # Handle 0.0.0.0 case (all DHCP)
            if start_ip == "0.0.0.0" and end_ip == "0.0.0.0":
                continue  # Skip this, means no static pool
            
            try:
                start = ip_lib.ip_address(start_ip)
                end = ip_lib.ip_address(end_ip)
                
                if start > end:
                    raise forms.ValidationError(f"Invalid range: {start_ip} → {end_ip}. Start IP must be less than or equal to end IP.")
                
                pools.append(f"{start}-{end}")
            except ValueError as e:
                raise forms.ValidationError(f"Invalid IP address: '{start_ip}' or '{end_ip}'. {str(e)}")
        
        return pools

    def clean(self):
        cleaned_data = super().clean()
        network = cleaned_data.get("network")
        static_pools = cleaned_data.get("static_pools_input", [])
        gateway = cleaned_data.get("gateway")
        
        if network and static_pools:
            # Verify all static IPs are within the subnet
            import ipaddress as ip_lib
            try:
                net = ip_lib.ip_network(network, strict=False)
                for pool_range in static_pools:
                    start_ip, end_ip = pool_range.split('-')
                    start = ip_lib.ip_address(start_ip.strip())
                    end = ip_lib.ip_address(end_ip.strip())
                    
                    if start not in net or end not in net:
                        raise forms.ValidationError(f"Static IP range {pool_range} is outside the subnet {network}")
            except (ValueError, AttributeError) as e:
                raise forms.ValidationError(f"Error validating static pools: {str(e)}")
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        static_pools = self.cleaned_data.get("static_pools_input", [])
        
        # Save static pools
        instance.static_ip_pools = static_pools if static_pools else None
        
        # Calculate and save DHCP pools
        if instance.network:
            instance.dhcp_pools = instance.calculate_dhcp_pools()
        
        if commit:
            instance.save()
        return instance


SUBNET_CONFIG = CRUDConfig(
    model=Subnet,
    form_class=SubnetForm,
    list_url_name="overwatch:subnet_list",
    create_url_name="overwatch:subnet_create",
    edit_url_name="overwatch:subnet_edit",
    delete_url_name="overwatch:subnet_delete",
    template_prefix="overwatch/subnet",
    entity_name="subnet",
)


def tag_list(request: HttpRequest) -> HttpResponse:
    tags = Tag.objects.all().order_by("name")
    total_all_count = tags.count()

    query = request.GET.get("q")
    if query:
        tags = tags.filter(Q(name__icontains=query) | Q(description__icontains=query))

    filtered_count = tags.count()
    pagination = paginate_queryset(tags, request)

    context = {
        **pagination,
        "query": query or "",
        "filtered_count": filtered_count,
        "total_all_count": total_all_count,
    }

    template = get_htmx_template(request, "overwatch/tag_list_partial.html", "overwatch/tag_list.html")
    return render(request, template, context)


def tag_create(request: HttpRequest) -> HttpResponse:
    return generic_create_view(request, TAG_CONFIG)


def tag_edit(request: HttpRequest, pk: int) -> HttpResponse:
    return generic_edit_view(request, pk, TAG_CONFIG)


def tag_delete(request: HttpRequest, pk: int) -> HttpResponse:
    return generic_delete_view(request, pk, TAG_CONFIG)


def category_list(request: HttpRequest) -> HttpResponse:
    categories = Category.objects.all().order_by("device_type")
    total_all_count = categories.count()

    query = request.GET.get("q")
    if query:
        categories = categories.filter(device_type__icontains=query)

    filtered_count = categories.count()
    pagination = paginate_queryset(categories, request)

    context = {
        **pagination,
        "query": query or "",
        "filtered_count": filtered_count,
        "total_all_count": total_all_count,
        "form": CategoryForm(),
    }

    template = get_htmx_template(request, "overwatch/category_list_partial.html", "overwatch/category_list.html")
    return render(request, template, context)


def category_create(request: HttpRequest) -> HttpResponse:
    return generic_create_view(request, CATEGORY_CONFIG)


def category_edit(request: HttpRequest, pk: int) -> HttpResponse:
    return generic_edit_view(request, pk, CATEGORY_CONFIG)


def category_delete(request: HttpRequest, pk: int) -> HttpResponse:
    return generic_delete_view(request, pk, CATEGORY_CONFIG)


def subnet_list(request: HttpRequest) -> HttpResponse:
    subnets = Subnet.objects.all().order_by("name")
    total_all_count = subnets.count()

    query = request.GET.get("q")
    if query:
        subnets = subnets.filter(
            Q(name__icontains=query)
            | Q(network__icontains=query)
            | Q(gateway__icontains=query)
            | Q(description__icontains=query)
        )

    vlan_filter = request.GET.get("vlan")
    if vlan_filter:
        try:
            subnets = subnets.filter(vlan_id=int(vlan_filter))
        except ValueError:
            pass

    filtered_count = subnets.count()
    pagination = paginate_queryset(subnets, request)

    # Add IP calculations to each subnet
    for subnet in pagination["page_obj"]:
        subnet.usable_ips = subnet.get_usable_ips()
        subnet.available_ips = subnet.get_available_ips()
        subnet.allocation_percentage = subnet.get_allocation_percentage()
        subnet.static_ip_count = subnet.get_static_ip_count()
        subnet.dhcp_ip_count = subnet.get_dhcp_ip_count()

    context = {
        **pagination,
        "query": query or "",
        "vlan_filter": vlan_filter or "",
        "filtered_count": filtered_count,
        "total_all_count": total_all_count,
    }

    template = get_htmx_template(request, "overwatch/subnet_list_partial.html", "overwatch/subnet_list.html")
    return render(request, template, context)


def subnet_create(request: HttpRequest) -> HttpResponse:
    return generic_create_view(request, SUBNET_CONFIG)


def subnet_edit(request: HttpRequest, pk: int) -> HttpResponse:
    return generic_edit_view(request, pk, SUBNET_CONFIG)


def subnet_delete(request: HttpRequest, pk: int) -> HttpResponse:
    return generic_delete_view(request, pk, SUBNET_CONFIG)


def subnet_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """View subnet details in a modal."""
    subnet = get_object_or_404(Subnet, pk=pk)
    
    context = {
        "subnet": subnet,
        "usable_ips": subnet.get_usable_ips(),
        "available_ips": subnet.get_available_ips(),
        "allocation_percentage": subnet.get_allocation_percentage(),
        "static_ip_count": subnet.get_static_ip_count(),
        "dhcp_ip_count": subnet.get_dhcp_ip_count(),
    }
    
    return render(request, "overwatch/subnet_detail_modal.html", context)


# =============================================================================
# IPAM VIEWS
# =============================================================================

class IPAMForm(forms.ModelForm):
    class Meta:
        model = IPAM
        fields = ["ip_address", "subnet", "status", "server", "mac_address", "description", "active"]
        widgets = {
            "ip_address": forms.TextInput(attrs={"class": FORM_INPUT_CLASS, "placeholder": "e.g. 192.168.1.10"}),
            "subnet": forms.Select(attrs={"class": FORM_SELECT_CLASS}),
            "status": forms.Select(attrs={"class": FORM_SELECT_CLASS}),
            "server": forms.Select(attrs={"class": FORM_SELECT_CLASS}),
            "mac_address": forms.TextInput(attrs={"class": FORM_INPUT_CLASS, "placeholder": "e.g. 00:11:22:33:44:55"}),
            "description": forms.Textarea(attrs={"class": FORM_TEXTAREA_CLASS, "rows": 3}),
            "active": forms.CheckboxInput(attrs={"class": FORM_CHECKBOX_CLASS}),
        }


IPAM_CONFIG = CRUDConfig(
    model=IPAM,
    form_class=IPAMForm,
    list_url_name="overwatch:ipam_list",
    create_url_name="overwatch:ipam_create",
    edit_url_name="overwatch:ipam_edit",
    delete_url_name="overwatch:ipam_delete",
    template_prefix="overwatch/ipam",
    entity_name="IP address",
)


def ipam_list(request: HttpRequest) -> HttpResponse:
    """Database-driven IPAM view - shows static and DHCP IP allocations."""
    import ipaddress as ip_lib
    
    # Get filter parameters
    query = request.GET.get("q", "")
    subnet_filter = request.GET.get("subnet", "")
    status_filter = request.GET.get("status", "")
    ip_type_filter = request.GET.get("ip_type", "")
    
    # Get all subnets for filter dropdown
    subnets = Subnet.objects.all().order_by("name")
    
    # Build IPAM query
    ipam_records = IPAM.objects.select_related("subnet", "server")
    
    # Filter by subnet
    selected_subnet = None
    if subnet_filter:
        ipam_records = ipam_records.filter(subnet_id=subnet_filter)
        selected_subnet = subnets.filter(pk=subnet_filter).first()
    
    # Filter by status
    if status_filter:
        ipam_records = ipam_records.filter(status=status_filter)
    
    # Filter by IP type
    if ip_type_filter:
        ipam_records = ipam_records.filter(ip_type=ip_type_filter)
    
    # Search filter (IP, hostname, MAC)
    if query:
        ipam_records = ipam_records.filter(
            Q(ip_address__icontains=query) |
            Q(hostname__icontains=query) |
            Q(mac_address__icontains=query) |
            Q(server__hostname__icontains=query)
        )
    
    # Fetch all and sort by IP address numerically
    ipam_list_data = []
    try:
        for ipam in ipam_records:
            ipam_list_data.append({
                'id': ipam.id,
                'ip_address': ipam.ip_address,
                'ip_int': int(ip_lib.ip_address(ipam.ip_address)),  # For sorting
                'subnet_id': ipam.subnet.id if ipam.subnet else None,
                'subnet_name': ipam.subnet.name if ipam.subnet else '',
                'subnet_network': ipam.subnet.network if ipam.subnet else '',
                'status': ipam.status,
                'ip_type': ipam.ip_type,
                'active': ipam.active,
                'hostname': ipam.hostname,
                'mac_address': ipam.mac_address,
                'server_id': ipam.server_id if ipam.server else None,
                'is_bmc': ipam.is_bmc,
                'description': ipam.description,
                'updated_by': ipam.updated_by.username if ipam.updated_by else None,
                'updated_at': ipam.updated_at,
            })
        # Sort numerically by IP
        ipam_list_data.sort(key=lambda x: x['ip_int'])
    except Exception as e:
        print(f"Error sorting IPs: {e}")
    
    # Calculate stats
    total_ips = len(ipam_list_data)
    available = sum(1 for ip in ipam_list_data if ip['status'] == "available")
    assigned = sum(1 for ip in ipam_list_data if ip['status'] == "assigned")
    reserved = sum(1 for ip in ipam_list_data if ip['status'] == "reserved")
    
    # Check if this is an HTMX request for partial update
    if request.headers.get('HX-Request') == 'true':
        # Return partial template with just the table
        context = {
            "ipam_records": ipam_list_data,
            "total_ips": total_ips,
            "stats": {
                "available": available,
                "assigned": assigned,
                "reserved": reserved,
            },
        }
        return render(request, "overwatch/ipam_list_partial.html", context)
    
    context = {
        "query": query,
        "subnet_filter": subnet_filter,
        "status_filter": status_filter,
        "ip_type_filter": ip_type_filter,
        "subnets": subnets,
        "selected_subnet": selected_subnet,
        "ipam_records": ipam_list_data,
        "total_ips": total_ips,
        "stats": {
            "available": available,
            "assigned": assigned,
            "reserved": reserved,
        },
        "status_choices": IPAM_STATUS_CHOICES,
    }
    
    return render(request, "overwatch/ipam_list.html", context)


def ipam_available_ips(request: HttpRequest, subnet_id: int) -> JsonResponse:
    """Get available IPs for a subnet (for reservation modal)."""
    import ipaddress as ip_lib
    
    try:
        # Get available IPs from this subnet
        available_ips = IPAM.objects.filter(
            subnet_id=subnet_id,
            status="available"
        ).order_by("ip_address")
        
        # Sort numerically
        ip_list = []
        for ipam in available_ips:
            try:
                ip_list.append({
                    'id': ipam.id,
                    'ip_address': ipam.ip_address,
                    'ip_int': int(ip_lib.ip_address(ipam.ip_address))
                })
            except:
                pass
        
        ip_list.sort(key=lambda x: x['ip_int'])
        
        # Remove ip_int from response
        for ip in ip_list:
            del ip['ip_int']
        
        return JsonResponse({'ips': ip_list})
    except Exception as e:
        return JsonResponse({'ips': [], 'error': str(e)})


def ipam_reserve(request: HttpRequest) -> JsonResponse:
    """Reserve one or more IP addresses."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'})
    
    try:
        ip_ids = request.POST.getlist('ip_ids')
        note = request.POST.get('note', '').strip()
        
        print(f"DEBUG: ip_ids={ip_ids}, note={note}")  # Debug logging
        
        if not ip_ids:
            return JsonResponse({'success': False, 'message': 'No IPs selected'})
        
        if not note:
            return JsonResponse({'success': False, 'message': 'Note is required'})
        
        # Update all selected IPs
        updated_count = 0
        errors = []
        for ip_id in ip_ids:
            try:
                ipam = IPAM.objects.get(id=ip_id, status='available')
                ipam.status = 'reserved'
                ipam.description = note
                ipam.updated_by = request.user
                ipam.save()
                updated_count += 1
                print(f"DEBUG: Reserved IP {ipam.ip_address}")  # Debug logging
            except IPAM.DoesNotExist:
                errors.append(f"IP ID {ip_id} not found or not available")
                continue
            except Exception as e:
                errors.append(f"Error with IP ID {ip_id}: {str(e)}")
                continue
        
        if updated_count > 0:
            return JsonResponse({
                'success': True,
                'message': f'{updated_count} IP(s) reserved successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': f'No IPs were available for reservation. Errors: {", ".join(errors)}'
            })
    
    except Exception as e:
        print(f"DEBUG: Exception in ipam_reserve: {str(e)}")  # Debug logging
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'Server error: {str(e)}'})


def ipam_create(request: HttpRequest) -> HttpResponse:
    return generic_create_view(request, IPAM_CONFIG)


def ipam_unreserve(request: HttpRequest, pk: int) -> JsonResponse:
    """Unreserve an IP address - only creator or superuser can do this."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'})
    
    try:
        ipam = IPAM.objects.get(pk=pk)
        
        # Check if IP is reserved
        if ipam.status != 'reserved':
            return JsonResponse({'success': False, 'message': 'IP is not reserved'})
        
        # Check permissions - only creator or superuser can unreserve
        if not (request.user.is_superuser or ipam.updated_by == request.user):
            return JsonResponse({
                'success': False,
                'message': 'You do not have permission to unreserve this IP. Only the user who reserved it or a superuser can unreserve.'
            }, status=403)
        
        # Unreserve the IP
        ipam.status = 'available'
        ipam.description = None
        ipam.updated_by = request.user
        ipam.save()
        
        print(f"DEBUG: IP {ipam.ip_address} unreserved by {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'message': f'IP {ipam.ip_address} unreserved successfully'
        })
    
    except IPAM.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'IP not found'}, status=404)
    except Exception as e:
        print(f"DEBUG: Error in ipam_unreserve: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'Server error: {str(e)}'}, status=500)


def ipam_my_reserved_ips(request: HttpRequest) -> JsonResponse:
    """Fetch IPs reserved by the logged-in user."""
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Invalid method'})
    
    try:
        # Get all IPs reserved by current user
        reserved_ips = IPAM.objects.filter(
            status='reserved',
            updated_by=request.user
        ).select_related('subnet').order_by('ip_address')
        
        ips_data = []
        for ipam in reserved_ips:
            ips_data.append({
                'id': ipam.id,
                'ip_address': str(ipam.ip_address),
                'subnet': ipam.subnet.network if ipam.subnet else 'N/A',
                'description': ipam.description or '',
                'status': ipam.status,
                'hostname': ipam.hostname or '—'
            })
        
        return JsonResponse({
            'success': True,
            'ips': ips_data,
            'count': len(ips_data)
        })
    
    except Exception as e:
        print(f"DEBUG: Error in ipam_my_reserved_ips: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Server error: {str(e)}'}, status=500)


def ipam_release_ips(request: HttpRequest) -> JsonResponse:
    """Release (unreserve) one or more IPs reserved by the logged-in user."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid method'})
    
    try:
        ip_ids = request.POST.getlist('ip_ids')
        
        if not ip_ids:
            return JsonResponse({'success': False, 'message': 'No IPs selected'})
        
        # Release all selected IPs (only if user is creator)
        released_count = 0
        errors = []
        
        for ip_id in ip_ids:
            try:
                ipam = IPAM.objects.get(id=ip_id, status='reserved', updated_by=request.user)
                ipam.status = 'available'
                ipam.description = None
                ipam.updated_by = request.user
                ipam.save()
                released_count += 1
            except IPAM.DoesNotExist:
                errors.append(f"IP ID {ip_id} not found or not reserved by you")
                continue
            except Exception as e:
                errors.append(f"Error with IP ID {ip_id}: {str(e)}")
                continue
        
        if released_count > 0:
            return JsonResponse({
                'success': True,
                'message': f'{released_count} IP(s) released successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': f'No IPs were released. Errors: {", ".join(errors)}'
            })
    
    except Exception as e:
        print(f"DEBUG: Exception in ipam_release_ips: {str(e)}")
        return JsonResponse({'success': False, 'message': f'Server error: {str(e)}'}, status=500)


def ipam_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """Custom IPAM edit with permission checking for reserved IPs."""
    try:
        ipam = IPAM.objects.get(pk=pk)
        
        # Check permissions for reserved IPs
        if ipam.status == 'reserved':
            # Only creator (updated_by) or superuser can edit reserved IPs
            if not (request.user.is_superuser or ipam.updated_by == request.user):
                return HttpResponse(
                    '<div class="p-4 text-red-600 font-medium">❌ You do not have permission to edit this reserved IP. Only the user who reserved it or a superuser can make changes.</div>',
                    status=403
                )
        
        # Handle POST (form submission)
        if request.method == 'POST':
            form = IPAMForm(request.POST, instance=ipam)
            if form.is_valid():
                old_status = ipam.status
                ipam = form.save(commit=False)
                new_status = form.cleaned_data['status']
                
                # If status changed from reserved to available, clear description
                if old_status == 'reserved' and new_status == 'available':
                    ipam.description = None
                    print(f"DEBUG: Unreserving IP {ipam.ip_address} - clearing description")
                
                ipam.updated_by = request.user
                ipam.save()
                
                print(f"DEBUG: IP {ipam.ip_address} updated - status: {old_status} → {new_status}")
                
                # Return success response
                return HttpResponse(
                    '<div class="p-4 text-green-600 font-medium">✓ IP updated successfully</div>',
                    headers={'HX-Trigger': 'ipamUpdated'}
                )
            else:
                # Return form errors
                error_html = '<div class="p-4 text-red-600"><strong>Form errors:</strong><ul>'
                for field, errors in form.errors.items():
                    error_html += f'<li>{field}: {", ".join(errors)}</li>'
                error_html += '</ul></div>'
                return HttpResponse(error_html, status=400)
        
        # Handle GET (show form)
        else:
            form = IPAMForm(instance=ipam)
        
        context = {
            'form': form,
            'instance': ipam,
            'model_name': 'IPAM',
            'can_edit_reserved': ipam.status != 'reserved' or request.user.is_superuser or ipam.updated_by == request.user,
        }
        return render(request, 'overwatch/ipam_form_inner.html', context)
    
    except IPAM.DoesNotExist:
        return HttpResponse('<div class="p-4 text-red-600">❌ IP not found</div>', status=404)
    except Exception as e:
        print(f"DEBUG: Error in ipam_edit: {str(e)}")
        import traceback
        traceback.print_exc()
        return HttpResponse(f'<div class="p-4 text-red-600">❌ Error: {str(e)}</div>', status=500)


def ipam_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Custom IPAM delete with permission checking for reserved IPs."""
    try:
        ipam = IPAM.objects.get(pk=pk)
        
        # Check permissions for reserved IPs
        if ipam.status == 'reserved':
            # Only creator or superuser can delete reserved IPs
            if not (request.user.is_superuser or ipam.updated_by == request.user):
                return JsonResponse({
                    'success': False,
                    'message': 'You do not have permission to delete this reserved IP.'
                }, status=403)
        
        return generic_delete_view(request, pk, IPAM_CONFIG)
    
    except IPAM.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'IP not found'}, status=404)


import re
import ipaddress


def validate_ip_address(value: str) -> bool:
    """Validate IPv4 or IPv6 address format."""
    if not value:
        return True  # Empty is allowed (optional field)
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def validate_mac_address(value: str) -> bool:
    """Validate MAC address format (accepts various formats)."""
    if not value:
        return True  # Empty is allowed (optional field)
    # Remove common separators and check if it's a valid hex string
    clean_mac = re.sub(r'[:\-\.]', '', value)
    if len(clean_mac) != 12:
        return False
    try:
        int(clean_mac, 16)
        return True
    except ValueError:
        return False


def validate_uuid(value: str) -> bool:
    """Validate UUID format."""
    if not value:
        return True  # Empty is allowed (optional field)
    uuid_pattern = re.compile(
        r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
    )
    return bool(uuid_pattern.match(value))


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
            "category": forms.Select(attrs={"class": FORM_SELECT_CLASS}),
            "uuid": forms.TextInput(attrs={"class": FORM_INPUT_CLASS, "placeholder": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"}),
            "hostname": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
            "ip_address": forms.TextInput(attrs={"class": FORM_INPUT_CLASS, "placeholder": "192.168.1.1"}),
            "nic_mac": forms.TextInput(attrs={"class": FORM_INPUT_CLASS, "placeholder": "AA:BB:CC:DD:EE:FF"}),
            "bmc_ip": forms.TextInput(attrs={"class": FORM_INPUT_CLASS, "placeholder": "192.168.1.2"}),
            "bmc_mac": forms.TextInput(attrs={"class": FORM_INPUT_CLASS, "placeholder": "AA:BB:CC:DD:EE:FF"}),
            "manufacture": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
            "product_name": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
            "cpu": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
            "core_count": forms.NumberInput(attrs={"class": FORM_INPUT_CLASS, "min": "0", "max": "1024"}),
            "sockets": forms.NumberInput(attrs={"class": FORM_INPUT_CLASS, "min": "0", "max": "64"}),
            "total_mem": forms.NumberInput(attrs={"class": FORM_INPUT_CLASS, "min": "0", "max": "65536"}),
            "disk_count": forms.NumberInput(attrs={"class": FORM_INPUT_CLASS, "min": "0", "max": "256"}),
            "bios_version": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
            "bios_release_date": forms.DateInput(attrs={"type": "date", "class": FORM_INPUT_CLASS}),
            "os": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
            "os_version": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
            "kernel": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
            "building": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
            "room": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
            "rack": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
            "location": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
            "status": forms.Select(attrs={"class": FORM_SELECT_CLASS}),
            "assign_to": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
            "last_login": forms.TextInput(attrs={"class": FORM_INPUT_CLASS}),
            "data_source": forms.Select(attrs={"class": FORM_SELECT_CLASS}),
            "pdu_connection": forms.CheckboxInput(attrs={"class": FORM_CHECKBOX_CLASS}),
            "pdu_ip": forms.TextInput(attrs={"class": FORM_INPUT_CLASS, "placeholder": "192.168.1.100"}),
            "pdu_port_number": forms.TextInput(attrs={"class": FORM_INPUT_CLASS, "placeholder": "1-24"}),
        }

    def clean_ip_address(self):
        """Validate IP address format."""
        value = self.cleaned_data.get("ip_address", "")
        if value and not validate_ip_address(value):
            raise forms.ValidationError("Invalid IP address format. Example: 192.168.1.1 or 2001:db8::1")
        return value

    def clean_bmc_ip(self):
        """Validate BMC IP address format."""
        value = self.cleaned_data.get("bmc_ip", "")
        if value and not validate_ip_address(value):
            raise forms.ValidationError("Invalid BMC IP address format. Example: 192.168.1.2")
        return value

    def clean_pdu_ip(self):
        """Validate PDU IP address format."""
        value = self.cleaned_data.get("pdu_ip", "")
        if value and not validate_ip_address(value):
            raise forms.ValidationError("Invalid PDU IP address format. Example: 192.168.1.100")
        return value

    def clean_nic_mac(self):
        """Validate NIC MAC address format."""
        value = self.cleaned_data.get("nic_mac", "")
        if value and not validate_mac_address(value):
            raise forms.ValidationError("Invalid MAC address format. Examples: AA:BB:CC:DD:EE:FF, aa-bb-cc-dd-ee-ff, or aabbccddeeff")
        return value.upper() if value else value  # Normalize to uppercase

    def clean_bmc_mac(self):
        """Validate BMC MAC address format."""
        value = self.cleaned_data.get("bmc_mac", "")
        if value and not validate_mac_address(value):
            raise forms.ValidationError("Invalid MAC address format. Examples: AA:BB:CC:DD:EE:FF, aa-bb-cc-dd-ee-ff, or aabbccddeeff")
        return value.upper() if value else value  # Normalize to uppercase

    def clean_uuid(self):
        """Validate UUID format."""
        value = self.cleaned_data.get("uuid", "")
        if value and not validate_uuid(value):
            raise forms.ValidationError("Invalid UUID format. Example: 550e8400-e29b-41d4-a716-446655440000")
        return value.lower() if value else value  # Normalize to lowercase

    def clean_core_count(self):
        """Validate core count is within reasonable range."""
        value = self.cleaned_data.get("core_count")
        if value is not None:
            if value < 0:
                raise forms.ValidationError("Core count cannot be negative.")
            if value > 1024:
                raise forms.ValidationError("Core count seems too high. Maximum is 1024.")
        return value

    def clean_sockets(self):
        """Validate socket count is within reasonable range."""
        value = self.cleaned_data.get("sockets")
        if value is not None:
            if value < 0:
                raise forms.ValidationError("Socket count cannot be negative.")
            if value > 64:
                raise forms.ValidationError("Socket count seems too high. Maximum is 64.")
        return value

    def clean_total_mem(self):
        """Validate memory is within reasonable range (in GB)."""
        value = self.cleaned_data.get("total_mem")
        if value is not None:
            if value < 0:
                raise forms.ValidationError("Memory cannot be negative.")
            if value > 65536:
                raise forms.ValidationError("Memory seems too high. Maximum is 65536 GB (64 TB).")
        return value

    def clean_disk_count(self):
        """Validate disk count is within reasonable range."""
        value = self.cleaned_data.get("disk_count")
        if value is not None:
            if value < 0:
                raise forms.ValidationError("Disk count cannot be negative.")
            if value > 256:
                raise forms.ValidationError("Disk count seems too high. Maximum is 256.")
        return value

    def clean_hostname(self):
        """Validate hostname format."""
        value = self.cleaned_data.get("hostname", "")
        if value:
            # Hostname should be alphanumeric with hyphens and dots allowed
            hostname_pattern = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$')
            if not hostname_pattern.match(value):
                raise forms.ValidationError("Invalid hostname format. Use alphanumeric characters, hyphens, and dots only.")
            if len(value) > 253:
                raise forms.ValidationError("Hostname is too long. Maximum 253 characters.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        pdu_connection = cleaned_data.get("pdu_connection")
        pdu_ip = cleaned_data.get("pdu_ip")
        pdu_port_number = cleaned_data.get("pdu_port_number")

        if pdu_connection:
            if not pdu_ip:
                self.add_error("pdu_ip", "PDU IP is required when PDU Connection is enabled.")
            if not pdu_port_number:
                self.add_error("pdu_port_number", "PDU Port # is required when PDU Connection is enabled.")

        return cleaned_data


class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ["content", "priority", "is_public"]
        widgets = {
            "content": forms.Textarea(attrs={"rows": 3, "class": FORM_TEXTAREA_CLASS}),
            "priority": forms.Select(attrs={"class": FORM_SELECT_CLASS}),
            "is_public": forms.CheckboxInput(attrs={"class": FORM_CHECKBOX_CLASS}),
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
            if request.user.is_authenticated:
                note.updated_by = request.user
            note.save()
    return redirect("overwatch:server_detail", pk=pk)


def server_note_edit(request: HttpRequest, pk: int, note_pk: int) -> HttpResponse:
    from .models import Note
    note = get_object_or_404(Note, pk=note_pk, server_id=pk)
    # Only the note owner can edit
    if request.method == "POST":
        if request.user.is_authenticated and request.user == note.updated_by:
            note.content = request.POST.get("content", note.content)
            note.priority = request.POST.get("priority", note.priority)
            note.is_public = "is_public" in request.POST
            note.save()
    return redirect("overwatch:server_detail", pk=pk)


def server_note_delete(request: HttpRequest, pk: int, note_pk: int) -> HttpResponse:
    from .models import Note
    note = get_object_or_404(Note, pk=note_pk, server_id=pk)
    # Only the note owner can delete
    if request.method == "POST":
        if request.user.is_authenticated and request.user == note.updated_by:
            note.delete()
    return redirect("overwatch:server_detail", pk=pk)


# =============================================================================
# REST API VIEWSETS
# =============================================================================


class ServerViewSet(viewsets.ModelViewSet):
    """API endpoint for Server CRUD operations."""

    queryset = Server.objects.all().prefetch_related("tags").select_related("category")
    serializer_class = ServerSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["hostname", "ip_address", "uuid", "status", "os", "manufacture", "category"]
    search_fields = ["hostname", "ip_address", "uuid", "manufacture", "product_name"]
    ordering_fields = ["hostname", "created_at", "updated_at"]
    ordering = ["-created_at"]

    @action(detail=False, methods=["post"])
    def bulk_create(self, request):
        """Create multiple servers at once."""
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def update_status(self, request, pk=None):
        """Update server status."""
        server = self.get_object()
        new_status = request.data.get("status")
        if new_status not in dict(Server._meta.get_field("status").choices):
            return Response({"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
        server.status = new_status
        server.save()
        return Response(self.get_serializer(server).data)


class CategoryViewSet(viewsets.ModelViewSet):
    """API endpoint for Category CRUD operations."""

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["device_type"]
    search_fields = ["device_type"]
    ordering = ["device_type"]


class TagViewSet(viewsets.ModelViewSet):
    """API endpoint for Tag CRUD operations."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name", "description"]
    ordering = ["name"]


class SubnetViewSet(viewsets.ModelViewSet):
    """API endpoint for Subnet CRUD operations."""

    queryset = Subnet.objects.all()
    serializer_class = SubnetSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name", "network", "description"]
    ordering = ["name"]

