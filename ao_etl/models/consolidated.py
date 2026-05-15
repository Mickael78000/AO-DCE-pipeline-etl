"""Modèle de données pour la consolidation LLM d'un marché public.

Schéma de sortie JSON strict conforme à la spec de consolidation métier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional


ConfidenceLevel = Literal["high", "medium", "low"]
FieldStatus = Literal["found", "inferred", "missing"]


@dataclass
class ConsolidatedField:
    value: Optional[object]
    status: FieldStatus
    confidence: ConfidenceLevel
    justification: str

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "status": self.status,
            "confidence": self.confidence,
            "justification": self.justification,
        }

    @classmethod
    def missing(cls, justification: str = "") -> "ConsolidatedField":
        return cls(value=None, status="missing", confidence="low",
                   justification=justification)


@dataclass
class SourceTrace:
    source_file: str
    source_platform: str
    source_url: Optional[str]
    input_reference: Optional[str]

    def to_dict(self) -> dict:
        return {
            "source_file": self.source_file,
            "source_platform": self.source_platform,
            "source_url": self.source_url,
            "input_reference": self.input_reference,
        }


@dataclass
class ConsolidationControl:
    manual_review_required: bool
    review_reasons: List[str]
    quality_flags: List[str]

    def to_dict(self) -> dict:
        return {
            "manual_review_required": self.manual_review_required,
            "review_reasons": self.review_reasons,
            "quality_flags": self.quality_flags,
        }


@dataclass
class ConsolidatedRecord:
    """Enregistrement consolidé complet issu du LLM."""

    record_id: str
    source_trace: SourceTrace

    reference: ConsolidatedField = field(default_factory=lambda: ConsolidatedField.missing())
    title: ConsolidatedField = field(default_factory=lambda: ConsolidatedField.missing())
    buyer_final: ConsolidatedField = field(default_factory=lambda: ConsolidatedField.missing())
    buyer_type: ConsolidatedField = field(default_factory=lambda: ConsolidatedField.missing())
    fonction_publique: ConsolidatedField = field(default_factory=lambda: ConsolidatedField.missing())
    fonction_publique_detail: ConsolidatedField = field(default_factory=lambda: ConsolidatedField.missing())
    procedure_label: ConsolidatedField = field(default_factory=lambda: ConsolidatedField.missing())
    procedure_family: ConsolidatedField = field(default_factory=lambda: ConsolidatedField.missing())
    formalisation_type: ConsolidatedField = field(default_factory=lambda: ConsolidatedField.missing())
    contract_nature: ConsolidatedField = field(default_factory=lambda: ConsolidatedField.missing())
    ccag_type: ConsolidatedField = field(default_factory=lambda: ConsolidatedField.missing())
    cpv_main: ConsolidatedField = field(default_factory=lambda: ConsolidatedField.missing())
    cpv_list: ConsolidatedField = field(default_factory=lambda: ConsolidatedField(
        value=[], status="missing", confidence="low", justification=""))
    location_final: ConsolidatedField = field(default_factory=lambda: ConsolidatedField.missing())
    deadline_final: ConsolidatedField = field(default_factory=lambda: ConsolidatedField.missing())
    duration_initial: ConsolidatedField = field(default_factory=lambda: ConsolidatedField.missing())
    renewals: ConsolidatedField = field(default_factory=lambda: ConsolidatedField.missing())
    estimated_amount: ConsolidatedField = field(default_factory=lambda: ConsolidatedField.missing())

    control: ConsolidationControl = field(default_factory=lambda: ConsolidationControl(
        manual_review_required=False, review_reasons=[], quality_flags=[]))

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "source_trace": self.source_trace.to_dict(),
            "final_fields": {
                "reference": self.reference.to_dict(),
                "title": self.title.to_dict(),
                "buyer_final": self.buyer_final.to_dict(),
                "buyer_type": self.buyer_type.to_dict(),
                "fonction_publique": self.fonction_publique.to_dict(),
                "fonction_publique_detail": self.fonction_publique_detail.to_dict(),
                "procedure_label": self.procedure_label.to_dict(),
                "procedure_family": self.procedure_family.to_dict(),
                "formalisation_type": self.formalisation_type.to_dict(),
                "contract_nature": self.contract_nature.to_dict(),
                "ccag_type": self.ccag_type.to_dict(),
                "cpv_main": self.cpv_main.to_dict(),
                "cpv_list": self.cpv_list.to_dict(),
                "location_final": self.location_final.to_dict(),
                "deadline_final": self.deadline_final.to_dict(),
                "duration_initial": self.duration_initial.to_dict(),
                "renewals": self.renewals.to_dict(),
                "estimated_amount": self.estimated_amount.to_dict(),
            },
            "control": self.control.to_dict(),
        }

    def to_flat_dict(self) -> dict:
        """Sérialisation plate pour export CSV — une colonne par champ métier."""
        d: dict = {
            "record_id": self.record_id,
            "source_file": self.source_trace.source_file,
            "source_platform": self.source_trace.source_platform,
            "source_url": self.source_trace.source_url or "",
        }
        field_names = [
            "reference", "title", "buyer_final", "buyer_type",
            "fonction_publique", "fonction_publique_detail",
            "procedure_label", "procedure_family", "formalisation_type",
            "contract_nature", "ccag_type", "cpv_main", "cpv_list",
            "location_final", "deadline_final", "duration_initial",
            "renewals", "estimated_amount",
        ]
        for fname in field_names:
            cf: ConsolidatedField = getattr(self, fname)
            val = cf.value
            if isinstance(val, list):
                val = "|".join(str(x) for x in val)
            d[fname] = val if val is not None else ""
            d[fname + "_status"] = cf.status
            d[fname + "_confidence"] = cf.confidence
        d["manual_review_required"] = self.control.manual_review_required
        d["review_reasons"] = "|".join(self.control.review_reasons)
        d["quality_flags"] = "|".join(self.control.quality_flags)
        return d
