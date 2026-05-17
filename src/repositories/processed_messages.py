from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.processed_messages import ProcessedMessageModel


class ProcessedMessagesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def is_processed(self, event_id: UUID) -> bool:
        result = await self.session.execute(
            select(ProcessedMessageModel.id).where(ProcessedMessageModel.event_id == event_id)
        )
        return result.first() is not None

    async def mark_processed(self, *, event_id: UUID, topic: str) -> None:
        stmt = (
            pg_insert(ProcessedMessageModel)
            .values(event_id=event_id, topic=topic)
            .on_conflict_do_nothing(index_elements=["event_id"])
        )
        await self.session.execute(stmt)
        await self.session.flush()
