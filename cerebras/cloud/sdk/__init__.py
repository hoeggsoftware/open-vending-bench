"""Stub module for Cerebras SDK used in tests.

The real Cerebras SDK provides a `Cerebras` client class with a
`chat.completions.create` method that returns an object whose
`choices[0].message.content` contains the generated text.

Our test suite patches ``cerebras.cloud.sdk.Cerebras`` with a mock, so
the implementation only needs to exist – it never gets executed.  The
minimal stub below satisfies the import and provides the attributes the
code expects, raising a clear error if the stub is used inadvertently.
"""


class _ChatCompletions:
    def create(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError(
            "Cerebras SDK stub: 'create' should be mocked in tests."
        )


class _Chat:
    def __init__(self):
        self.completions = _ChatCompletions()


class Cerebras:
    """Stub Cerebras client.

    The constructor stores the API key and provides a ``chat`` attribute
    mimicking the real SDK structure.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.chat = _Chat()
