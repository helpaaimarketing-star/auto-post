from processing.data_processor import DataProcessor
from processing.rule_engine import RuleEngine


def __getattr__(name):
    if name == "ModelHandler":
        from ai_agent import AIAgent
        return AIAgent
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = ["ModelHandler", "DataProcessor", "RuleEngine"]
