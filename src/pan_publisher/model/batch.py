from uuid import uuid4

from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from src.pan_publisher.model import Base
from src.pan_publisher.model.annotation import Annotation


class AnnotationBatchEntry(Base):
    id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, unique=True, nullable=False
    )
    annotation_id = Column(UUID(), ForeignKey(Annotation.id))
