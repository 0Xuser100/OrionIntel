from  pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    model_config=SettingsConfigDict(env_file=".env",env_file_encoding="utf-8")
    APP_NAME: str
    APP_VERSION: str
    APP_VENDOR:str
    OPENAI_API_KEY: str




def get_settings():
    return Settings()