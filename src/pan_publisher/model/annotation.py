from uuid import uuid4

import dateutil.parser
from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID

from pan_publisher.model import Base


class Annotation(Base):
    context = ["https://pan.network/annotation/v1"]
    credential_type = ["VerifiableCredential", "PANCredential"]
    id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, unique=True, nullable=False
    )

    # issuer data
    issuer = Column(String(42), nullable=False)
    issuance_date = Column(DateTime(), nullable=False)

    # annotation data
    subject_id = Column(String(50), nullable=False, unique=True)
    original_content = Column(Text(), nullable=False)
    annotation_content = Column(Text(), nullable=True)
    batch_id = Column(UUID(as_uuid=True), default=None, nullable=True)

    # proof data
    proof_type = "EthereumECDSA"
    proof_purpose = "PANSubmission"
    proof_date = Column(DateTime(), nullable=False)
    verification_method = Column(String(200), nullable=False)
    proof_jws = Column(Text(), nullable=False)

    published = Column(Boolean(), default=False)

    def get_annotation_id(self):
        return f"urn:uuid:{self.id}"

    def get_issuer(self):
        return f"urn:ethereum:{self.issuer}"

    def get_issuance_date(self):
        return self.issuance_date.isoformat()

    def get_subject_id(self):
        return f"urn:cid:{self.subject_id}"

    def get_proof_date(self):
        return self.proof_date.isoformat()

    def get_verification_method(self):
        return f"urn:ethereum:{self.verification_method}"

    def to_dict(self):
        return {
            "@context": self.context,
            "id": self.get_annotation_id(),
            "type": self.credential_type,
            "issuer": self.get_issuer(),
            "issuanceDate": self.get_issuance_date(),
            "credentialSubject": {
                "id": self.get_subject_id(),
                "content": self.original_content,
                "annotation": self.annotation_content,
            },
            "proof": {
                "type": self.proof_type,
                "created": self.get_proof_date(),
                "proofPurpose": self.proof_purpose,
                "verificationMethod": self.get_verification_method(),
                "jws": self.proof_jws,
            },
            "published": self.published,
        }

    @classmethod
    def from_dict(cls, candidate):
        return cls(
            context=candidate["@context"],
            credential_type=candidate["type"],
            issuer=candidate["issuer"].split(":")[2],
            issuance_date=dateutil.parser.parse(candidate["issuanceDate"]),
            original_content=candidate["credentialSubject"]["content"],
            annotation_content=candidate["credentialSubject"]["annotation"],
            proof_type=candidate["proof"]["type"],
            proof_date=dateutil.parser.parse(candidate["proof"]["created"]),
            proof_purpose=candidate["proof"]["proofPurpose"],
            verification_method=candidate["proof"]["verificationMethod"],
            proof_jws=candidate["proof"]["jws"],
        )

    def __repr__(self):
        return f"<Annotation(annotation_id='{self.annotation_id}', subject_id='{self.subject_id}')>"
