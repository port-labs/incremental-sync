from pydantic_settings import BaseSettings


class _AppSettings(BaseSettings):
    AZURE_CLIENT_ID: str
    AZURE_CLIENT_SECRET: str
    PORT_CLIENT_ID: str
    PORT_CLIENT_SECRET: str
    PORT_API_URL: str = "https://api.getport.io/v1"


app_settings = _AppSettings()


__all__ = ["app_settings"]
