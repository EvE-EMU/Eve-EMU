from django.utils.html import format_html


def list_2_html_w_tooltips(my_items: list, max_items: int) -> str:
    """converts list of strings into HTML with cutoff and tooltip"""
    items_truncated_str = ', '.join(my_items[:max_items])
    if not my_items:
        result = None
    elif len(my_items) <= max_items:
        result = items_truncated_str
    else:
        items_truncated_str += ', (...)'
        items_all_str = ', '.join(my_items)
        result = format_html(
            '<span data-tooltip="{}" class="tooltip">{}</span>',
            items_all_str,
            items_truncated_str
        )
    return result
