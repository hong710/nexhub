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

    page_size = request.GET.get("page_size")
    try:
        page_size = int(page_size) if page_size else 25
    except ValueError:
        page_size = 25
    if page_size not in [25, 50, 100, 200]:
        page_size = 25

    page_sizes = [25, 50, 100, 200]

    paginator = Paginator(servers, page_size)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    elided_pages = paginator.get_elided_page_range(number=page_obj.number, on_each_side=1, on_ends=1)

    table_headers = [
        ("hostname", "Hostname"),
        ("ip_address", "IP"),
        ("bmc_ip", "BMC IP"),
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

    context = {
        "page_obj": page_obj,
        "query": query or "",
        "table_headers": table_headers,
        "page_size": page_size,
        "page_sizes": page_sizes,
        "elided_pages": elided_pages,
    }

    template = "overwatch/server_list_partial.html" if request.headers.get("HX-Request") else "overwatch/server_list.html"
    return render(request, template, context)


def server_detail(request: HttpRequest, pk: int) -> HttpResponse:
    server = get_object_or_404(Server, pk=pk)
    return render(request, "overwatch/server_detail.html", {"server": server})
