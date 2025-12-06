from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from .models import Server


def server_list(request: HttpRequest) -> HttpResponse:
    """
    Simple server list with search, filter, sort, and pagination.
    HTMX can update the table body without reloading the whole page.
    """

    total_all_count = Server.objects.count()
    servers = Server.objects.all()

    # Search across many visible fields
    query = request.GET.get("q")
    if query:
        q_digit = query.isdigit()
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
