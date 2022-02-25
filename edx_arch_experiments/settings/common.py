def plugin_settings(settings):
    """Default settings values."""
    env_tokens = getattr(settings, 'ENV_TOKENS', {})
    settings.SCHEMA_REGISTRY_URL = env_tokens.get('SCHEMA_REGISTRY_URL', '')
    settings.SCHEMA_REGISTRY_API_KEY = env_tokens.get('SCHEMA_REGISTRY_API_KEY', '')
    settings.SCHEMA_REGISTRY_API_SECRET = env_tokens.get('SCHEMA_REGISTRY_API_SECRET', '')
    settings.KAFKA_BOOTSTRAP_SERVER = env_tokens.get('KAFKA_BOOTSTRAP_SERVER', '')
    settings.KAFKA_API_KEY = env_tokens.get('KAFKA_API_KEY', '')
    settings.KAFKA_API_SECRET = env_tokens.get('KAFKA_API_SECRET', '')