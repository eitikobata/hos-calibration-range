"""
boto3's DynamoDB resource layer refuses plain Python floats outright -
it raises TypeError rather than silently losing precision, which is the
right call from AWS but means every float coming out of Pydantic
(model_dump()) has to be converted to Decimal before it can be written.
This was caught by the test suite on the first run, not assumed.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any


def to_dynamo_safe(value: Any) -> Any:
    """Recursively convert float -> Decimal so dict/list structures from
    Pydantic's model_dump() can be written straight into a DynamoDB item."""
    if isinstance(value, float):
        # str() first, not Decimal(value) directly - going through str
        # avoids inheriting float's own binary-representation imprecision
        # (e.g. Decimal(0.1) != Decimal("0.1")).
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_dynamo_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_dynamo_safe(v) for v in value]
    return value
