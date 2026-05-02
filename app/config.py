import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GHOSTFOLIO_HOST: str = os.getenv("GHOSTFOLIO_HOST", "https://ghostfol.io/").rstrip("/")
    GHOSTFOLIO_TOKEN: str = os.getenv("GHOSTFOLIO_TOKEN", "")
    BASE_URL: str = os.getenv("BASE_URL", "/").rstrip("/")

    @property
    def has_token(self) -> bool:
        return bool(self.GHOSTFOLIO_TOKEN and self.GHOSTFOLIO_TOKEN != "your_access_token_here")


settings = Settings()
