from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Anthropic
    anthropic_api_key: str

    # GitHub
    github_token: str
    github_webhook_secret: str

    # Jira (all optional)
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""

    # Review behaviour
    review_pass_threshold: int = 6  # rating >= this → commit status "success"

    @property
    def jira_enabled(self) -> bool:
        return bool(self.jira_base_url and self.jira_email and self.jira_api_token)


settings = Settings()
