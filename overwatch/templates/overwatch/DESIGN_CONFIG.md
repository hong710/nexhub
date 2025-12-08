# Design Configuration Guide

This file documents the reusable design patterns used in the Dictionary pages that can be applied to other similar pages (Tag, Category, etc.).

## Design Patterns Overview

All CRUD (Create, Read, Update, Delete) list pages follow a consistent pattern based on the Dictionary implementation.

---

## 1. List Page Structure (`*_list.html`)

### Base Template
- Extends: `components/list_page.html`
- Block structure includes: `page_title`, `list_icon`, `list_heading`, `list_filters`, `list_actions`, `list_target_id`, `list_table`, `list_scripts`, `list_modals`

### Key Components:

#### A. Page Header Icon
```html
{% block list_icon %}
<svg xmlns="http://www.w3.org/2000/svg" class="h-7 w-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
    <!-- Custom icon path here -->
</svg>
{% endblock %}
```

#### B. Search & Filter Form
- Form ID: `{prefix}-filters` (e.g., `dict-filters`)
- HTMX attributes:
  - `hx-get="."` - Submits to current URL
  - `hx-target="#{prefix}-table"` - Updates table container
  - `hx-trigger="keyup changed delay:250ms from:#{prefix}-search, change from:.{prefix}-filter-select, submit"`
  - `hx-swap="outerHTML"`

#### C. Filter Elements
1. **Search Input**
   - ID: `{prefix}-search`
   - Name: `q`
   - Classes: `w-80 bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500`

2. **Filter Selects**
   - Class: `{prefix}-filter-select`
   - Base classes: `bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500`

3. **Reset Button**
   - ID: `{prefix}-reset`
   - Contains reset icon SVG
   - Classes: `inline-flex items-center gap-1 px-4 py-2 text-sm font-medium text-gray-900 bg-white border border-gray-300 rounded-lg hover:bg-gray-100`

#### D. Action Buttons
```html
{% block list_actions %}
<a href="#"
   data-modal-target="{prefix}-modal"
   data-modal-toggle="{prefix}-modal"
   data-title="Add {entity}"
   hx-get="{% url 'overwatch:{entity}_create' %}"
   hx-target="#{prefix}-modal-body"
   hx-swap="innerHTML"
   class="{prefix}-modal-open inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-700 rounded-lg hover:bg-blue-800">
    <svg><!-- Plus icon --></svg>
    Add {entity}
</a>
{% endblock %}
```

#### E. JavaScript Event Handlers
Pattern for all list pages:
1. Attach modal open handlers
2. Page size selector change listener
3. Reset button click handler
4. Delete confirmation handlers
5. HTMX afterSwap re-attachment

---

## 2. Table Partial (`*_list_partial.html`)

### Container Structure
```html
<div id="{prefix}-table" class="relative flex flex-col h-full overflow-hidden rounded-lg border border-slate-200 shadow-inner">
    <div class="flex-1 overflow-auto">
        <table class="min-w-full table-auto text-sm text-left text-gray-700">
            <!-- Table content -->
        </table>
    </div>
    <!-- Pagination footer -->
</div>
```

### Table Header
- Classes: `text-xs uppercase bg-blue-800 text-white sticky top-0 z-30`
- Header cells: `px-4 py-3 font-semibold align-top border-r border-blue-900 whitespace-nowrap`
- Last header: No right border (`border-blue-900` removed)

### Table Body
- Body classes: `bg-white divide-y divide-gray-200`
- Row hover: `hover:bg-blue-50`
- Cell classes: `px-4 py-2 text-[12px] text-slate-700 border-r border-slate-200`
- Counter cell: `text-center w-12` with `{{ forloop.counter0|add:page_obj.start_index }}`

### Action Column
- Edit button:
  ```html
  <a href="#"
     data-modal-target="{prefix}-modal"
     data-modal-toggle="{prefix}-modal"
     data-title="Edit {entity}"
     hx-get="{% url 'overwatch:{entity}_edit' item.pk %}"
     hx-target="#{prefix}-modal-body"
     hx-swap="innerHTML"
     class="{prefix}-modal-open font-medium text-blue-700 hover:underline">
      Edit
  </a>
  ```

- Delete button:
  ```html
  <button type="button"
          class="font-medium text-red-600 hover:underline {prefix}-delete-btn"
          data-delete-url="{% url 'overwatch:{entity}_delete' item.pk %}"
          data-label="{{ item.name }}">
      Delete
  </button>
  ```

### Pagination Footer
- Container: `flex flex-col md:flex-row md:items-center md:justify-between gap-3 border-t border-slate-200 bg-white px-3 py-3 flex-shrink-0`
- Includes: Page info, navigation buttons, page size selector, record count

---

## 3. Form Modal Inner (`*_form_inner.html`)

### Structure
```html
<div class="space-y-4">
    <form method="post" action="{{ form_action|default:request.path }}" class="space-y-4">
        {% csrf_token %}
        <!-- Form fields in grid layout -->
        <div class="flex items-center gap-3 pt-2">
            <button type="submit" class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm px-4 py-2 text-center">
                {{ submit_label|default:"Save" }}
            </button>
            <button type="button" data-modal-hide="{prefix}-modal" class="text-sm text-gray-700 hover:underline">Cancel</button>
        </div>
    </form>
</div>
```

### Field Layout
- Grid: `grid grid-cols-1 md:grid-cols-2 gap-4`
- Label: `block text-sm font-medium text-slate-700 mb-1`
- Error display: `text-xs text-red-600 mt-1`

---

## 4. Standalone Form Page (`*_form.html`)

### Structure
```html
{% extends "base.html" %}
{% block title %}Add {Entity} - NexHub{% endblock %}
{% block content %}
<div class="bg-white h-full flex flex-col overflow-hidden rounded-lg border border-slate-200 shadow">
    <div class="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
        <div class="flex items-center gap-2 text-blue-900">
            <svg><!-- Icon --></svg>
            <h1 class="text-lg font-semibold text-slate-900">{{ form_title|default:"Add {entity}" }}</h1>
        </div>
        <a href="{% url 'overwatch:{entity}_list' %}" class="text-sm text-blue-700 hover:underline">Back to list</a>
    </div>
    <div class="p-6 overflow-auto">
        {% include "overwatch/{entity}_form_inner.html" %}
    </div>
</div>
{% endblock %}
```

---

## 5. Color Palette

### Primary Colors
- Blue Primary: `bg-blue-700`, `hover:bg-blue-800`, `text-blue-700`
- Blue Dark (Table Header): `bg-blue-800`
- Blue Border: `border-blue-900` (table header cells)

### Neutral Colors
- Background: `bg-white`, `bg-gray-50`
- Border: `border-slate-200`, `border-gray-300`
- Text: `text-slate-700`, `text-slate-800`, `text-gray-900`

### Semantic Colors
- Success: `bg-green-100`, `text-green-700`, `border-green-200`
- Danger: `text-red-600`
- Hover: `hover:bg-blue-50`

---

## 6. Typography

- Headings: `text-lg font-semibold text-slate-900`
- Table headers: `text-xs uppercase`
- Table cells: `text-[12px]`
- Form labels: `text-sm font-medium text-slate-700`
- Form inputs: `text-sm`

---

## 7. Spacing

- Section padding: `px-6 py-4` or `p-4`
- Gap between elements: `gap-2`, `gap-3`, `gap-4`
- Form field spacing: `space-y-4`

---

## 8. JavaScript Naming Convention

Replace `{prefix}` with the entity identifier (e.g., `dict`, `tag`, `category`):

- Modal ID: `{prefix}-modal`
- Modal title ID: `{prefix}-modal-title`
- Modal body ID: `{prefix}-modal-body`
- Delete modal ID: `{prefix}-delete-modal`
- Delete form ID: `{prefix}-delete-form`
- Table container ID: `{prefix}-table`
- Filter form ID: `{prefix}-filters`
- Search input ID: `{prefix}-search`
- Page size select ID: `{prefix}-page-size`
- Reset button ID: `{prefix}-reset`
- CSS class for modal triggers: `{prefix}-modal-open`
- CSS class for delete buttons: `{prefix}-delete-btn`
- CSS class for filter selects: `{prefix}-filter-select`

---

## 9. HTMX Patterns

### List Filtering
```html
hx-get="."
hx-target="#{prefix}-table"
hx-trigger="keyup changed delay:250ms from:#{prefix}-search, change from:.{prefix}-filter-select, submit"
hx-swap="outerHTML"
```

### Modal Loading
```html
hx-get="{% url 'overwatch:{entity}_create' %}"
hx-target="#{prefix}-modal-body"
hx-swap="innerHTML"
hx-trigger="click"
```

---

## 10. Django View Pattern

### List View
```python
def {entity}_list(request: HttpRequest) -> HttpResponse:
    items = {Model}.objects.all().order_by("{sort_field}")
    total_all_count = items.count()
    
    # Search filter
    query = request.GET.get("q")
    if query:
        items = items.filter(Q(...) | Q(...))
    
    # Additional filters...
    
    filtered_count = items.count()
    
    # Pagination
    page_size = int(request.GET.get("page_size", 25))
    page_sizes = [25, 50, 100, 200]
    paginator = Paginator(items, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    elided_pages = paginator.get_elided_page_range(...)
    
    context = {...}
    
    template = "{entity}_list_partial.html" if request.headers.get("HX-Request") else "{entity}_list.html"
    return render(request, template, context)
```

### Create/Edit/Delete Views
Follow the same pattern as `dictionary_create`, `dictionary_edit`, `dictionary_delete`

---

## How to Apply to New Pages

1. Copy Dictionary template files
2. Replace all instances of `dict` with your entity prefix (e.g., `tag`, `category`)
3. Replace `dictionary` with your entity name
4. Update table columns to match your model fields
5. Update form fields to match your model
6. Adjust filters based on your requirements
7. Update view functions following the pattern above
8. Update URLs with correct naming

---

## Consistency Checklist

- [ ] All IDs use consistent `{prefix}-` naming
- [ ] All CSS classes follow the same pattern
- [ ] HTMX attributes are properly configured
- [ ] JavaScript event handlers are attached
- [ ] Modal configurations match
- [ ] Pagination structure is identical
- [ ] Table styling is consistent
- [ ] Form styling matches
- [ ] Colors follow the defined palette
- [ ] Typography follows the standards

---

## 11. Detail Modal Pattern

For entities that need a detail view modal (e.g., Subnet, Server):

### Structure
```html
<!-- Detail Modal -->
<div id="{prefix}-detail-modal" tabindex="-1" aria-hidden="true" 
     class="hidden overflow-y-auto overflow-x-hidden fixed inset-0 z-50 flex justify-center items-center w-full h-full bg-gray-900/50">
    <div class="relative p-4 w-full max-w-4xl max-h-full">
        <div class="relative bg-white rounded-lg shadow-sm">
            <div class="flex items-center justify-between p-4 md:p-5 border-b rounded-t border-gray-200">
                <h3 class="text-xl font-semibold text-gray-900">{Entity} Details</h3>
                <button type="button" onclick="close{Entity}DetailModal()" class="...">Close</button>
            </div>
            <div id="{prefix}-detail-content" class="p-4 md:p-5">
                <!-- Detail content loaded via fetch -->
            </div>
        </div>
    </div>
</div>
```

### JavaScript for Detail Modal
```javascript
function init{Entity}DetailLinks() {
    document.querySelectorAll('.{prefix}-detail-link').forEach(function(link) {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const id = this.dataset.{prefix}Id;
            if (id) {
                fetch('/{entities}/' + id + '/')
                    .then(response => response.text())
                    .then(html => {
                        document.getElementById('{prefix}-detail-content').innerHTML = html;
                        const modal = document.getElementById('{prefix}-detail-modal');
                        modal.classList.remove('hidden');
                        modal.classList.add('flex');
                    });
            }
        });
    });
}
```

---

## 12. Dynamic Form Fields Pattern

For forms with dynamic input fields (e.g., IP Pool ranges):

### Structure
```html
<!-- Dynamic Fields Container -->
<div>
    <label class="block text-sm font-medium text-slate-700 mb-1">Field Label</label>
    
    <!-- Usage Hints Box -->
    <div class="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-800">
        <p class="font-semibold mb-1">💡 How to use:</p>
        <ul class="list-disc list-inside space-y-0.5">
            <li><strong>Option 1:</strong> Description...</li>
            <li><strong>Option 2:</strong> Description...</li>
        </ul>
    </div>
    
    <!-- Hidden field for JSON data -->
    <input type="hidden" name="field_data" id="field-data" value="{{ form.initial_data_json|default:'[]' }}">
    
    <!-- Dynamic rows container -->
    <div id="field-container" class="space-y-2 mb-2"></div>
    
    <!-- Add button -->
    <button type="button" id="add-field-btn" class="inline-flex items-center px-3 py-1.5 text-xs font-medium text-blue-700 bg-blue-100 rounded hover:bg-blue-200">
        <svg class="w-3 h-3 mr-1"><!-- Plus icon --></svg>
        Add Item
    </button>
</div>
```

### JavaScript for Dynamic Fields
```javascript
// Execute scripts loaded via innerHTML
modalBody.querySelectorAll('script').forEach(oldScript => {
    const newScript = document.createElement('script');
    if (oldScript.src) {
        newScript.src = oldScript.src;
    } else {
        newScript.textContent = oldScript.textContent;
    }
    oldScript.parentNode.replaceChild(newScript, oldScript);
});
```

---

## 13. Tag-Style Display Pattern

For displaying lists as tags/chips:

### Static IP Pools (Purple Theme)
```html
<div class="flex flex-wrap gap-2">
    {% for item in items %}
    <span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-mono bg-purple-100 text-purple-800 border border-purple-200 shadow-sm">
        <span class="inline-block w-2 h-2 rounded-full bg-purple-500"></span>
        {{ item }}
    </span>
    {% endfor %}
</div>
```

### DHCP Pools (Cyan Theme)
```html
<div class="flex flex-wrap gap-2">
    {% for item in items %}
    <span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-mono bg-cyan-100 text-cyan-800 border border-cyan-200 shadow-sm">
        <span class="inline-block w-2 h-2 rounded-full bg-cyan-500"></span>
        {{ item }}
    </span>
    {% endfor %}
</div>
```

### Color Themes for Tags
| Type | Background | Text | Border | Dot |
|------|------------|------|--------|-----|
| Purple (Static) | `bg-purple-100` | `text-purple-800` | `border-purple-200` | `bg-purple-500` |
| Cyan (DHCP) | `bg-cyan-100` | `text-cyan-800` | `border-cyan-200` | `bg-cyan-500` |
| Indigo (VLAN) | `bg-indigo-100` | `text-indigo-800` | `border-indigo-200` | `bg-indigo-500` |
| Green (Success) | `bg-green-100` | `text-green-700` | `border-green-200` | `bg-green-500` |
| Red (Error) | `bg-red-100` | `text-red-700` | `border-red-200` | `bg-red-500` |

---

## 14. IP/Network Display Patterns

### In Table Cells
```html
<td class="px-4 py-2 text-[12px] text-slate-700 border-r border-slate-200">
    {% if item.pools %}
    <div class="flex items-center gap-2">
        <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-purple-100 text-purple-700 flex-shrink-0">
            {{ item.ip_count }} IPs
        </span>
        <div class="flex flex-wrap gap-1 flex-1 min-w-0">
            {% for pool in item.pools %}
            <span class="inline-flex items-center gap-1 bg-purple-50 rounded px-2 py-0.5 border border-purple-100">
                <span class="inline-block w-1.5 h-1.5 rounded-full bg-purple-500 flex-shrink-0"></span>
                <span class="font-mono text-[11px] text-purple-800 whitespace-nowrap">{{ pool }}</span>
            </span>
            {% endfor %}
        </div>
    </div>
    {% else %}
    <span class="text-slate-400 text-xs">—</span>
    {% endif %}
</td>
```

### In Detail Modal Cards
```html
<div class="bg-gradient-to-br from-purple-50 to-pink-50 rounded-lg border border-purple-200 p-4">
    <h3 class="text-sm font-semibold text-slate-700 mb-3 flex items-center gap-2">
        <svg class="h-4 w-4 text-purple-600"><!-- Icon --></svg>
        Static IP Pools ({{ count }} IPs)
    </h3>
    <div class="flex flex-wrap gap-2">
        {% for pool in pools %}
        <span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-mono bg-purple-100 text-purple-800 border border-purple-200 shadow-sm">
            <span class="inline-block w-2 h-2 rounded-full bg-purple-500"></span>
            {{ pool }}
        </span>
        {% endfor %}
    </div>
</div>
```
