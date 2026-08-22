from typing import Callable, List, Optional, Dict, Any
from datetime import datetime


class LazyPaginator:
    """
    Paginator with lazy loading of data from the database.
    Caches recently fetched pages in memory to reduce DB load.
    """

    def __init__(
        self,
        query_func: Callable,
        per_page: int = 10,
        cache_pages: int = 3,
        state: Optional[Dict] = None,
    ):
        """
        Args:
            query_func: Async callable ``(offset, limit) -> List`` or
                        ``(count_only=True) -> int``.
            per_page:   Items per page.
            cache_pages: Max number of pages to keep in the in-memory cache.
            state:       Previously serialised paginator state for restoration.
        """
        self.query_func = query_func
        self.per_page = per_page
        self.cache_pages = cache_pages

        if state and isinstance(state, dict):
            self._cache: Dict[int, List] = {}
            self._total_count: Optional[int] = state.get("total_count")
            self.current_page: int = state.get("current_page", 0)
        else:
            self._cache = {}
            self._total_count = None
            self.current_page = 0

    async def get_total_count(self) -> int:
        """Return the total item count, fetching it once and caching it."""
        if self._total_count is None:
            self._total_count = await self.query_func(count_only=True)
        return self._total_count

    async def get_page(self, page: int) -> List:
        """Fetch a page by number (0-indexed), using the cache when available."""
        self.current_page = page
        if page in self._cache:
            return self._cache[page]

        offset = page * self.per_page
        items = await self.query_func(offset=offset, limit=self.per_page)
        self._cache[page] = items

        if len(self._cache) > self.cache_pages:
            total_pages = await self.get_total_pages()
            pages_to_keep = set(range(max(0, page - 1), min(page + 2, total_pages)))
            for cached_page in list(self._cache.keys()):
                if cached_page not in pages_to_keep and len(self._cache) > self.cache_pages:
                    del self._cache[cached_page]

        return items

    async def get_total_pages(self) -> int:
        """Return the total number of pages (at least 1)."""
        total = await self.get_total_count()
        return max(1, (total + self.per_page - 1) // self.per_page)


    def get_state(self) -> Dict:
        """Serialise the current state for FSM storage (no cache — it contains ORM objects)."""
        return {"total_count": self._total_count, "current_page": self.current_page}

    def clear_cache(self):
        """Discard the in-memory page cache."""
        self._cache.clear()
        self._total_count = None
