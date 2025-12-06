"""Locust load test suite hitting every public endpoint on a fixed 10s cadence."""

import random
from typing import List

from locust import HttpUser, task, constant


SOURCE_KEYS = ["github", "hackernews", "producthunt"]
SEARCH_QUERIES = ["ai", "ml", "data", "cloud", "dev", "ops"]


class BaseUser(HttpUser):
    """Shared helpers for endpoint-specific load users."""

    wait_time = constant(10)
    startup_ids: List[int] = []

    def refresh_startup_ids(self) -> None:
        """Prime a pool of startup IDs from the API; safe to retry if empty."""
        with self.client.get(
            "/api/startups",
            params={"per_page": 50, "page": 1},
            name="/api/startups (seed)",
            catch_response=True,
        ) as resp:
            if not resp.ok:
                return
            payload = resp.json()
            items = payload.get("items") or []
            ids = [item.get("id") for item in items if isinstance(item, dict) and item.get("id")]
            if ids:
                self.startup_ids = ids

    def pick_startup_id(self) -> int:
        if not self.startup_ids:
            self.refresh_startup_ids()
        if not self.startup_ids:
            return 1
        return random.choice(self.startup_ids)


class HomeUser(BaseUser):
    @task
    def home(self) -> None:
        self.client.get("/", name="/")


class SourceUser(BaseUser):
    @task
    def by_source(self) -> None:
        source = random.choice(SOURCE_KEYS)
        self.client.get(f"/source/{source}", name="/source/:source")


class SearchPageUser(BaseUser):
    @task
    def search_page(self) -> None:
        query = random.choice(SEARCH_QUERIES)
        self.client.get("/search", params={"q": query, "per_page": 20}, name="/search")


class ToolUser(BaseUser):
    def on_start(self) -> None:
        self.refresh_startup_ids()

    @task
    def tool_detail(self) -> None:
        tool_id = self.pick_startup_id()
        self.client.get(f"/tool/{tool_id}", name="/tool/:id")


class ApiStartupsUser(BaseUser):
    @task
    def api_startups(self) -> None:
        page = random.randint(1, 3)
        per_page = random.choice([20, 50, 100])
        self.client.get(
            "/api/startups",
            params={"page": page, "per_page": per_page},
            name="/api/startups",
        )


class ApiSearchUser(BaseUser):
    @task
    def api_search(self) -> None:
        query = random.choice(SEARCH_QUERIES)
        per_page = random.choice([20, 50, 100])
        self.client.get(
            "/api/search",
            params={"q": query, "per_page": per_page},
            name="/api/search",
        )


class HealthUser(BaseUser):
    @task
    def health(self) -> None:
        self.client.get("/health", name="/health")
