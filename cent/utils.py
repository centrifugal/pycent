from .exceptions import ClientNotEmpty


def to_bytes(s):
    return s.encode("latin-1")


def check_not_empty_pipeline(func):
    def wrapper(self, *args, **kwargs):
        if self._messages:
            raise ClientNotEmpty("client command buffer not empty, send commands or reset client")
        res = func(self, *args, **kwargs)
        return res

    return wrapper
