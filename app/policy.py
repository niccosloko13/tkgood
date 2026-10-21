from dataclasses import dataclass

ALLOWED_ACTIONS = {
    "open_tiktok",
    "check_session",
    "search",
    "navigate",
    "open_result",
    "scroll",
    "read",
    "inspect",
    "extract",
    "screenshot",
    "copy_url",
    "go_back",
}

FORBIDDEN_ACTIONS = {
    "like",
    "dislike",
    "comment",
    "reply",
    "follow",
    "unfollow",
    "share",
    "repost",
    "save",
    "favorite",
    "message",
    "dm",
    "publish",
    "post",
    "edit_profile",
    "edit_account",
    "edit_settings",
    "edit_account/settings",
    "subscribe",
}

FORBIDDEN_TARGET_TERMS = {
    "like",
    "curtir",
    "comment",
    "comentar",
    "reply",
    "responder",
    "follow",
    "seguir",
    "unfollow",
    "deixar de seguir",
    "share",
    "compartilhar",
    "repost",
    "save",
    "salvar",
    "favorite",
    "favoritar",
    "message",
    "mensagem",
    "dm",
    "publish",
    "publicar",
}

@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str

class ReadOnlyPolicy:
    def check(self, action: str, target_text: str = "") -> PolicyDecision:
        action_normalized = action.strip().lower().replace(" ", "_")
        target_normalized = target_text.strip().lower()

        if action_normalized in FORBIDDEN_ACTIONS:
            return PolicyDecision(False, f"READ_ONLY: action '{action}' is forbidden.")

        if action_normalized not in ALLOWED_ACTIONS:
            return PolicyDecision(False, f"READ_ONLY: action '{action}' is not allow-listed.")

        if target_normalized:
            for term in FORBIDDEN_TARGET_TERMS:
                if term in target_normalized:
                    return PolicyDecision(
                        False,
                        f"READ_ONLY: target contains forbidden engagement term '{term}'.",
                    )

        return PolicyDecision(True, "Allowed by READ_ONLY policy.")
