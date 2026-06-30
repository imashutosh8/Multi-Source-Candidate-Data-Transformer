from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Union
from candidate_transformer.models.intermediate import IntermediateCandidate

class BaseExtractor(ABC):
    """
    Abstract Base Class for all candidate data extractors.
    Each extractor handles a specific format and outputs an IntermediateCandidate.
    """
    @abstractmethod
    def extract(self, source: Union[Path, str, Any]) -> IntermediateCandidate:
        """
        Extracts candidate data from a file path, string path, or file-like stream/buffer.

        Args:
            source (Union[Path, str, Any]): Source file path or readable stream.

        Returns:
            IntermediateCandidate: The intermediate candidate data.
        """
        pass
