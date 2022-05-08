from typing import List, Optional


class ParamsMixin:
    @staticmethod
    def get_publish_params(channel: str, data: dict, skip_history: bool = False) -> dict:
        params = {
            "channel": channel,
            "data": data,
            "skip_history": skip_history,
        }
        return params

    @staticmethod
    def get_broadcast_params(channels: List[str], data: dict, skip_history: bool = False) -> dict:
        params = {
            "channels": channels,
            "data": data,
            "skip_history": skip_history,
        }
        return params

    @staticmethod
    def get_subscribe_params(user: str, channel: str, client: Optional[str] = None) -> dict:
        params = {"user": user, "channel": channel}
        if client:
            params["client"] = client
        return params

    @staticmethod
    def get_unsubscribe_params(user: str, channel: str, client: Optional[str] = None) -> dict:
        params = {"user": user, "channel": channel}
        if client:
            params["client"] = client
        return params

    @staticmethod
    def get_disconnect_params(user: str, client: Optional[str] = None) -> dict:
        params = {"user": user}
        if client:
            params["client"] = client
        return params

    @staticmethod
    def get_presence_params(channel: str) -> dict:
        return {"channel": channel}

    @staticmethod
    def get_presence_stats_params(channel: str) -> dict:
        return {"channel": channel}

    @staticmethod
    def get_history_params(channel: str, limit: int = 0, since: Optional[dict] = None, reverse: bool = False) -> dict:
        params = {
            "channel": channel,
            "limit": limit,
            "reverse": reverse,
        }
        if since:
            params["since"] = {"offset": since["offset"], "epoch": since["epoch"]}
        return params

    @staticmethod
    def get_history_remove_params(channel: str) -> dict:
        return {"channel": channel}

    @staticmethod
    def get_channels_params(pattern: str = "") -> dict:
        return {"pattern": pattern}

    @staticmethod
    def get_info_params() -> dict:
        return {}
