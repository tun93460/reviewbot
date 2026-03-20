import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class AppConfig:
    gitlab_url: str = field(default_factory=lambda: os.getenv("GITLAB_URL", "https://gitlab.com"))
    gitlab_token: str = field(default_factory=lambda: os.getenv("GITLAB_TOKEN", ""))
    gitlab_username: str = field(default_factory=lambda: os.getenv("GITLAB_USERNAME", "").split("#", 1)[0].strip())

    def validate(self) -> list[str]:
        errors = []
        if not self.gitlab_token:
            errors.append("GITLAB_TOKEN is not set")
        return errors
