from dataclasses import dataclass, field, asdict
from typing import List, Optional

@dataclass
class ExampleDTO:
    key: str
    value: object

    @staticmethod
    def examples_dto(examples: List[str]):
        return ExampleDTO(
            key="examples dto string key",
            value=examples
        )

    @staticmethod
    def example_dto(example: str):
        return ExampleDTO(
            key="example dto string key",
            value=example
        )
