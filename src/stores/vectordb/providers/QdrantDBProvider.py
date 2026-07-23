from typing import List

from loguru import logger
from qdrant_client import QdrantClient, models

from models.db_schemes import RetrievedDocument

from ..VectorDBEnums import DistanceMethodEnums
from ..VectorDBInterface import VectorDBInterface


class QdrantDBProvider(VectorDBInterface):

    def __init__(
        self,
        distance_method: str,
        db_client: str = None,
        db_url: str = None,
        default_vector_size: int = 1536,
        index_threshold: int = 100,
    ):

        self.client = None
        self.db_client = db_client
        self.db_url = db_url
        self.distance_method = None
        self.default_vector_size = default_vector_size
        self.index_threshold = index_threshold

        if distance_method == DistanceMethodEnums.COSINE.value:
            self.distance_method = models.Distance.COSINE
        elif distance_method == DistanceMethodEnums.DOT.value:
            self.distance_method = models.Distance.DOT

        self.logger = logger

    async def connect(self):
        if self.db_url:
            self.client = QdrantClient(url=self.db_url)
        else:
            self.client = QdrantClient(path=self.db_client)

    async def disconnect(self):
        self.client = None

    async def is_collection_existed(self, collection_name: str) -> bool:
        return self.client.collection_exists(collection_name=collection_name)

    async def list_all_collections(self) -> List:
        return self.client.get_collections()

    async def get_collection_info(self, collection_name: str) -> dict:
        return self.client.get_collection(collection_name=collection_name)

    async def delete_collection(self, collection_name: str):
        if await self.is_collection_existed(collection_name):
            self.logger.info(f"Deleting collection: {collection_name}")
            return self.client.delete_collection(collection_name=collection_name)

    async def create_collection(
        self, collection_name: str, embedding_size: int, do_reset: bool = False
    ):
        if do_reset:
            _ = await self.delete_collection(collection_name=collection_name)

        if not await self.is_collection_existed(collection_name):
            self.logger.info(f"Creating new Qdrant collection: {collection_name}")

            _ = self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_size, distance=self.distance_method
                ),
            )

            return True

        return False

    async def insert_one(
        self,
        collection_name: str,
        text: str,
        vector: list,
        metadata: dict = None,
        record_id: str = None,
    ):

        if not await self.is_collection_existed(collection_name):
            self.logger.error(
                f"Can not insert new record to non-existed collection: {collection_name}"
            )
            return False

        try:
            _ = self.client.upload_points(
                collection_name=collection_name,
                points=[
                    models.PointStruct(
                        id=record_id,
                        vector=vector,
                        payload={"text": text, "metadata": metadata},
                    )
                ],
                wait=True,
            )
        except Exception as e:
            self.logger.error(f"Error while inserting batch: {e}")
            return False

        return True

    async def insert_many(
        self,
        collection_name: str,
        texts: list,
        vectors: list,
        metadata: list = None,
        record_ids: list = None,
        batch_size: int = 50,
    ):

        if not await self.is_collection_existed(collection_name):
            self.logger.error(
                f"Can not insert new record to non-existed collection: {collection_name}"
            )
            return False

        if metadata is None:
            metadata = [None] * len(texts)

        if record_ids is None:
            record_ids = list(range(0, len(texts)))

        for i in range(0, len(texts), batch_size):
            batch_end = i + batch_size

            batch_texts = texts[i:batch_end]
            batch_vectors = vectors[i:batch_end]
            batch_metadata = metadata[i:batch_end]
            batch_record_ids = record_ids[i:batch_end]

            batch_points = [
                models.PointStruct(
                    id=batch_record_ids[x],
                    vector=batch_vectors[x],
                    payload={"text": batch_texts[x], "metadata": batch_metadata[x]},
                )
                for x in range(len(batch_texts))
            ]

            try:
                _ = self.client.upload_points(
                    collection_name=collection_name,
                    points=batch_points,
                    wait=True,
                )
            except Exception as e:
                self.logger.error(f"Error while inserting batch: {e}")
                return False

        return True

    async def search_by_vector(
        self, collection_name: str, vector: list, limit: int = 5
    ):

        if not await self.is_collection_existed(collection_name):
            self.logger.error(
                f"Can not search non-existed collection: {collection_name}"
            )
            return []

        response = self.client.query_points(
            collection_name=collection_name,
            query=vector,
            limit=limit,
            with_payload=True,
        )

        return [
            RetrievedDocument(
                score=point.score,
                text=point.payload["text"],
            )
            for point in response.points
        ]
