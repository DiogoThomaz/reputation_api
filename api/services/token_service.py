import secrets


class TokenService:
    @staticmethod
    def generate_token() -> str:
        return secrets.token_urlsafe(48)
