"""
Compatibility entry point for the 3XSHOP architecture contract.
"""

from app.architecture.contracts import (
    ArchitectureComponent,
    ArchitectureContract,
    TenantContext,
    architecture_snapshot,
)

__all__ = [
    "ArchitectureComponent",
    "ArchitectureContract",
    "TenantContext",
    "architecture_snapshot",
]
