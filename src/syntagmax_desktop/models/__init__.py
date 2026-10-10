# SPDX-License-Identifier: MIT

# Author: Syntagmax Desktop
# Description: Qt model-view data models for the reviewer panels.

"""Qt model-view data models for the Syntagmax Desktop panels.

The models in this package adapt the public ``syntagmax.api`` result objects to
Qt's model-view framework, so a dense result — such as a large traceability
matrix — is rendered lazily through a model rather than eagerly materialised into
per-cell widgets (spec E6).
"""

from syntagmax_desktop.models.artifact_list_model import (
    AID_ROLE,
    IS_HEADER_ROLE,
    ArtifactListModel,
)
from syntagmax_desktop.models.trace_model import TraceTableModel

__all__ = ['AID_ROLE', 'IS_HEADER_ROLE', 'ArtifactListModel', 'TraceTableModel']
