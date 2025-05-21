from fastapi.responses import RedirectResponse
from pydantic import Field


class AuthenticationRedirectResponse(RedirectResponse):
    redirect_url: str = Field(
        description="The URL to redirect the user after successful or failed authentication.",
        examples=[
            "http://localhost:8001/auth/callback?state=xyz&client_id=123",
            "http://localhost:8001/auth/callback?error=401&error_description=Authorization failed.&state=xyz",
        ],
    )

    def __init__(self, redirect_url: str) -> None:
        super().__init__(url=redirect_url)
