import logging
import secrets

from pydantic_settings import BaseSettings

logger = logging.getLogger("hotelbot.config")

MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = {"extra": "allow", "env_file": ".env", "env_file_encoding": "utf-8"}

    app_name: str = "Hotel Guest Ops Bot"
    environment: str = "development"
    debug: bool = False

    # Optional commercial setting
    allow_th_block: bool = False

    database_url: str = "postgresql+psycopg2://user:password@localhost:5432/hotelbot"
    redis_url: str = "redis://localhost:6379/0"

    whatsapp_verify_token: str = ""
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_phone_number: str = ""  # For wa.me QR code links

    # Twilio WhatsApp API credentials (backup provider)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # LINE Messaging API credentials (optional global fallback)
    line_channel_access_token: str = ""
    line_channel_secret: str = ""

    # Cloudbeds PMS OAuth credentials
    cloudbeds_client_id: str = ""
    cloudbeds_client_secret: str = ""

    # Base URL for OAuth callbacks (e.g., https://yourdomain.com)
    base_url: str = ""

    # PMS Simulation Testing (optional)
    pms_simulation_test_phone: str = ""

    openai_api_key: str = ""
    openai_api_base: str = ""
    openai_model: str = ""

    # Public API base (for constructing webhooks)
    public_api_base_url: str = ""

    default_hotel_id: int = 1
    admin_token: str = ""
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    llm_timeout_seconds: int = 30
    llm_fallback_enabled: bool = True
    owner_api_token: str = ""
    resend_api_key: str = ""
    email_from_address: str = "no-reply@example.com"

    # Stripe Configuration
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_basic_price_id: str = ""
    stripe_basic_price_id_thb: str = ""
    stripe_basic_price_id_ron: str = ""
    stripe_pro_price_id: str = ""
    stripe_pro_price_id_thb: str = ""
    stripe_pro_price_id_ron: str = ""

    # Sentry Error Monitoring
    sentry_dsn: str = ""

    # Trusted proxy hosts for X-Forwarded-For (comma-separated, e.g. "172.18.0.1,10.0.0.1")
    trusted_proxy_hosts: str = ""


def get_settings() -> Settings:
    settings = Settings()

    # JWT Secret validation - ALWAYS enforce minimum length
    if len(settings.jwt_secret) < MIN_JWT_SECRET_LENGTH:
        if settings.environment in {"development", "test"}:
            # Auto-generate secure secret for dev/test
            settings.jwt_secret = secrets.token_urlsafe(48)
            logger.warning(
                "Generated random JWT secret for %s mode (not persistent across restarts)",
                settings.environment,
            )
        else:
            raise ValueError(
                f"JWT_SECRET must be at least {MIN_JWT_SECRET_LENGTH} characters in production. "
                f"Current length: {len(settings.jwt_secret)}. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )

    required_secrets = {
        "admin_token": settings.admin_token,
        "owner_api_token": settings.owner_api_token,
    }
    missing = [name for name, value in required_secrets.items() if not value]
    if settings.environment not in {"development", "test"} and missing:
        raise ValueError(
            f"Missing required secrets for environment {settings.environment}: {', '.join(missing)}"
        )
    if missing:
        logger.warning("Running with missing secrets (dev mode): %s", ", ".join(missing))
    return settings
