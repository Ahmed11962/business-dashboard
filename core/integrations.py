"""Provider contracts only; no fabricated integrations or enabled webhook endpoints.
Implementations require selected providers, official-documentation review, credentials,
sandbox validation, authenticated webhooks, replay protection and tenant authorization.
"""
from dataclasses import dataclass
from typing import Protocol

class IntegrationUnavailable(RuntimeError): pass

@dataclass(frozen=True)
class VerifiedSignatureEvent:
    provider: str
    external_event_id: str
    contract_reference: str
    signed_document_sha256: str
    completion_evidence_reference: str
    all_required_parties_signed: bool

class SignatureProvider(Protocol):
    def verify_webhook(self, raw_body: bytes, headers: dict[str,str]) -> VerifiedSignatureEvent:
        """Authenticate raw bytes before parsing; reject missing/invalid signatures."""
        ...
    def fetch_original_and_certificate(self, reference: str) -> tuple[bytes,bytes]: ...

class AccountingProvider(Protocol):
    def export_reconciled_entry(self, external_id: str, entry: dict) -> str:
        """Use idempotent source IDs; only one authoritative accounting system."""
        ...

class TaxInvoiceProvider(Protocol):
    def validate_and_issue(self, entity_id: str, invoice: dict) -> dict:
        """Requires reviewed VAT rules, entity numbering and applicable ZATCA validation."""
        ...

class DisabledIntegration:
    def __getattr__(self,name):
        raise IntegrationUnavailable('Provider not configured or validated. No external action was performed.')
