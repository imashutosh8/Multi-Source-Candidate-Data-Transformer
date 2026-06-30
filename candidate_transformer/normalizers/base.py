from abc import ABC, abstractmethod
from typing import Any

class BaseNormalizer(ABC):
    """
    Abstract Base Class for all normalizers.
    Each normalizer is responsible for standardizing a specific data type.
    """
    @abstractmethod
    def normalize(self, value: Any) -> Any:
        """
        Normalizes the given value into its canonical form.

        Args:
            value (Any): The raw value to normalize.

        Returns:
            Any: The normalized value.
        """
        pass
