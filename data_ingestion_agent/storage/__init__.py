"""Local storage repository package.

작성자 : 이영훈
담당 영역 : ai-agent
"""

from data_ingestion_agent.storage.local_repository import (
    LocalFileRepository,
    LocalWriteResult,
)

__all__ = ["LocalFileRepository", "LocalWriteResult"]
