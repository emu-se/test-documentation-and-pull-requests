from typing import Any

class Repository:
    def __init__(self, data: dict[str, Any]):
        self.full_name = data.get("full_name")
        self.stargazers_count = data.get("stargazers_count")
        self.forks_count = data.get("forks_count")
        self.watchers_count = data.get("watchers_count")
