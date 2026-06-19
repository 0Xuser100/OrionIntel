from controllers.BaseController import BaseController

from .providers import QdrantDBProvider
from .VectorDBEnums import VectorDBEnums


class VectorDBProviderFactory:
    def __init__(self, config):
        self.config = config
        self.base_controller = BaseController()

    def create(self, provider: str):
        if provider == VectorDBEnums.QDRANT.value:
            db_path = None
            if not self.config.VECTOR_DB_URL:
                db_path = self.base_controller.get_database_path(
                    db_name=self.config.VECTOR_DB_PATH
                )

            return QdrantDBProvider(
                distance_method=self.config.VECTOR_DB_DISTANCE_METHOD,
                db_path=db_path,
                db_url=self.config.VECTOR_DB_URL,
            )

        return None
