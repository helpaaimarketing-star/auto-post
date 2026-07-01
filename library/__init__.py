"""Custom library modules for SMMA Bot."""


def __getattr__(name):
    if name == "SocialMediaChecker":
        from social_checker import SocialMediaChecker
        return SocialMediaChecker
    elif name == "DealManager":
        from order_manager import DealManager
        return DealManager
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = ["SocialMediaChecker", "DealManager"]
