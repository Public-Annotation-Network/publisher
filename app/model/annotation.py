from sqlalchemy import Column, DateTime, Integer, String, Text

from app.model import Base


class Annotation(Base):
    context = ["https://pan.network/annotation/v1"]
    credential_type = ["VerifiableCredential", "PANCredential"]
    annotation_id = Column(Integer, primary_key=True)

    # issuer data
    issuer = Column(String(42), nullable=False)  # TODO: add issuer address validator
    issuance_date = Column(DateTime(), nullable=False)

    # annotation data
    subject_id = Column(String(50), nullable=False)
    original_content = Column(Text(), nullable=False)
    annotation_content = Column(Text(), nullable=True)

    # proof data
    proof_type = "EthereumECDSA"
    proof_purpose = "PANSubmission"
    proof_date = Column(DateTime(), nullable=False)
    verification_method = Column(String(42), nullable=False)
    proof_jws = Column(Text(), nullable=False)

    def get_annotation_id(self):
        return f"urn:uuid:{self.annotation_id}"

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
        }

    def __repr__(self):
        return f"<Annotation(annotation_id='{self.annotation_id}', subject_id='{self.subject_id}')>"
