from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.processed_messages import ProcessedMessageModel


class ProcessedMessagesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def try_mark_processed(self, *, event_id: UUID, topic: str) -> bool:
        stmt = (
            pg_insert(ProcessedMessageModel)
            .values(event_id=event_id, topic=topic)
            .on_conflict_do_nothing(index_elements=["event_id"])
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0
