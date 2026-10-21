import pytest

from app.safe_actions import SafeBrowserActions, TargetDescriptor, UnsafeTargetError


def test_safe_regular_result():
    actions = SafeBrowserActions()
    actions.assert_safe_target(
        TargetDescriptor(
            selector='a[href*="/video/"]',
            text="Portable vacuum review",
            role="link",
        )
    )


@pytest.mark.parametrize(
    "target",
    [
        TargetDescriptor(text="Like"),
        TargetDescriptor(text="Curtir"),
        TargetDescriptor(aria_label="Follow"),
        TargetDescriptor(title="Compartilhar"),
        TargetDescriptor(selector='button[data-e2e="comment-icon"]', text="Comment"),
        TargetDescriptor(text="Salvar"),
        TargetDescriptor(text="Mensagem"),
    ],
)
def test_engagement_targets_are_blocked(target):
    actions = SafeBrowserActions()
    with pytest.raises(UnsafeTargetError):
        actions.assert_safe_target(target)
