from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class UnknownTimeZoneError(Exception):
    pass


def timezone(name: str):
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise UnknownTimeZoneError(str(exc)) from exc
