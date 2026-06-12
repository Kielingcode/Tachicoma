def page_bounds(page: int, per_page: int) -> tuple[int, int]:
    if page < 1:
        page = 1
    start = (page - 1) * per_page
    return start, start + per_page


def total_pages(count: int, per_page: int) -> int:
    if count <= 0:
        return 0
    return (count + per_page - 1) // per_page
