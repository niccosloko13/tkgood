from __future__ import annotations

from dataclasses import dataclass

from .policy import FORBIDDEN_TARGET_TERMS, ReadOnlyPolicy


@dataclass(frozen=True)
class TargetDescriptor:
    selector: str = ""
    text: str = ""
    aria_label: str = ""
    title: str = ""
    role: str = ""


class UnsafeTargetError(PermissionError):
    pass


class SafeBrowserActions:
    """
    All future automated clicks must go through this class.

    It blocks engagement-like targets using visible text and common attributes.
    The current v0.1.2 does not perform autonomous TikTok clicks yet, but this
    becomes the mandatory gate for the Search Adapter.
    """

    def __init__(self):
        self.policy = ReadOnlyPolicy()

    @staticmethod
    def _normalized_target(target: TargetDescriptor) -> str:
        return " ".join(
            [
                target.selector,
                target.text,
                target.aria_label,
                target.title,
                target.role,
            ]
        ).strip().lower()

    def assert_safe_target(self, target: TargetDescriptor) -> None:
        combined = self._normalized_target(target)

        for term in FORBIDDEN_TARGET_TERMS:
            if term in combined:
                raise UnsafeTargetError(
                    f"READ_ONLY blocked target containing engagement term '{term}'."
                )

    def safe_click(self, locator, target: TargetDescriptor) -> None:
        self.assert_safe_target(target)

        decision = self.policy.check("open_result", combined_target(target))
        if not decision.allowed:
            raise UnsafeTargetError(decision.reason)

        locator.click()


def combined_target(target: TargetDescriptor) -> str:
    return " ".join(
        [
            target.selector,
            target.text,
            target.aria_label,
            target.title,
            target.role,
        ]
    )
