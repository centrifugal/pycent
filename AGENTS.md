# Working on cent

cent is the Python SDK for Centrifugo's HTTP server API, written to the
[Centrifugo server SDK specification](https://github.com/centrifugal/gocent/blob/master/spec.md),
whose reference implementation is gocent. Applications use it on their hot
paths and from both threads and asyncio, so it has to be correct under
concurrency and hard to misuse. Read this before changing code.

## Layout

| Path | What |
|---|---|
| `proto/api.proto`, `proto/proxy.proto` | Copies of Centrifugo's protos, from a released tag (`make sync-proto CENTRIFUGO_REF=v6.10.2`) |
| `gen/` | The generator: `proto.py` parses the protos, `generate.py` writes the code |
| `cent/_api.py`, `cent/proxy/_types.py` | Generated - never edited |
| `API.md` | The API reference, generated from the docstrings by `gen/api_docs.py` (`make docs`) - never edited |
| `cent/_client.py` | `Client` and `AsyncClient`: the two mirror each other line for line |
| `cent/_core.py` | What both clients share: configuration, headers, reading replies - no I/O |
| `cent/_wire.py`, `cent/_payload.py` | Encoding requests, decoding replies, payloads and `RawJSON` |
| `cent/_errors.py` | The exceptions and `retryable` |
| `cent/_broadcast.py`, `cent/_batch.py`, `cent/_autobatch.py`, `cent/_retry.py` | Broadcast results, batches, automatic batching, retries |
| `cent/_http.py` | The HTTP handlers' framework-free core and its ASGI and WSGI adapters |
| `cent/endpoints.py`, `cent/proxy/`, `cent/token.py`, `cent/sharedpoll.py` | Endpoints for client SDKs, proxy handlers, tokens, shared poll signatures |
| `tests/`, `tests/integration/` | Unit tests against a fake Centrifugo; integration tests against a real one |
| `testdata/` | The Centrifugo config and the Centrifugo PRO compose file the integration tests use |

## Invariants

These are not preferences. A change that breaks one is wrong even if every test
passes; if you find yourself about to break one, stop and say so instead.

1. **The generated files are never edited.** Change `proto/` or `gen/`, then
   `make generate`; `make generate-check` fails when they are stale. After a
   change to a docstring or the public API, `make docs` regenerates `API.md`;
   `make check` fails when it is stale.
2. **A call raises unless it did everything asked.** A broadcast or batch in
   which some parts failed raises `BroadcastFailedChannelsError` or
   `BatchFailedCommandsError`, whose `result` holds every part's outcome. A
   partial error is never an `ApiError` of its parts - also with one channel.
3. **Errors follow Centrifugo's model.** A Centrifugo error is an `ApiError`,
   raised as the subclass of its code when the code is known, and as `ApiError`
   itself otherwise. Centrifugo's transport error mode gives the same error as a
   200 reply.
4. **One deadline per call, with httpx2's public API only.** Its `timeout`,
   or `request_timeout`, bounds the call - the endpoint and token functions,
   connecting, the reply read. The async client wraps the call in
   `asyncio.timeout`. The blocking client gives httpx2 the time left as each
   request's timeout, which bounds each connect, read and write, and checks
   the deadline between the body's chunks; only headers trickling in can
   outlast it, which the README says. Any timeout raises `CentTimeoutError`.
5. **A payload is carried exactly.** A payload from a reply sent back unchanged
   is the same JSON value; `RawJSON` is sent as its text; NaN, infinities,
   bytes and invalid JSON never leave the client.
6. **A caller's HTTP client is never changed** - headers, pool, redirect
   policy: credentials and headers go on each request.
7. **Automatic batching never delays a call below `max_in_flight`**, never
   gives a caller a reply which is not its own, never sends a call whose caller
   gave up while it queued, and `close` waits for batches whose callers left. A
   batch runs in a context of its own - an empty `contextvars.Context` - which
   carries callers' values only through `batch_context`.
8. **`Client` and `AsyncClient` behave the same.** A change to one is made to
   the other, and the unit tests run each scenario against both (`Api` in
   `tests/test_client.py`).
9. **A handler answers with exactly one of result, error and disconnect,** as
   its proxy type can carry them; anything else is a 500 reported to
   `on_error`.

## Running things

```
make dev                 # install cent and the dev tools into env/
make check               # generated code, ruff, mypy --strict, unit tests: what CI runs
make test-integration    # against Centrifugo on :8100
```

The integration tests need a Centrifugo set up as `testdata/` says:

```
docker compose -f testdata/centrifugo-pro.compose.yml up -d --wait
PYCENT_TEST_PRO=1 make test-integration
```

They serve the proxy handlers on port 3100 and an API JWKS on 3101 of the host,
which Centrifugo reaches as `host.docker.internal`.

## Updating to a new Centrifugo API

1. `make sync-proto CENTRIFUGO_REF=vX.Y.Z` - always a released tag.
2. Read the diff of `proto/`: a removed field is a breaking change.
3. `make check`, then the integration tests against the new release.
4. Bump the Centrifugo image in `.github/workflows/ci.yml` and
   `testdata/centrifugo-pro.compose.yml`, and the versions table in the README
   when a feature needs the new release.

## Things that look wrong but are deliberate

- **httpx2, not httpx.** httpx stopped releasing in 2024; httpx2 is its
  maintained fork, the same API, which the ecosystem moved to. An httpx client
  passed in is refused with the fix in the message.
- **Keyword arguments, a method per API method**, as the spec says for Python
  (3.3): `client.publish(channel=..., data=...)`, `batch.publish(...)`,
  `cent.command.publish(...)`, keyword-only so that a field added to the protos
  cannot shift a call. The request dataclasses are internal: the generated
  methods build them, and the transport, automatic batching and retries take
  them.
- **Dataclasses, not pydantic models.** A pydantic type in the API would tie
  applications to one major version of it (spec 3.4, Stable).
- **A `timeout` parameter on async methods** (ruff's ASYNC109 is off): asyncio
  code cannot read an enclosing `asyncio.timeout`, so a call takes its own, and
  an outer one still ends it sooner.
- **`on_attempt_error` returns the wait, and raises to stop.** A callback which
  only logs - returning `None` - must not stop the retries by accident.
- **Only partial errors carry `result`.** A broadcast or batch failing as a
  whole raises its own error: its result would only say that every part failed
  with it.
- **Payloads are spliced into the request's JSON** behind random placeholders:
  `RawJSON` keeps its number text, and no string of the request can pass for a
  placeholder.
- **No deadline enforced inside httpx2.** A blocking request whose headers
  trickle in can outlast its timeout: bounding it would mean replacing httpx2
  internals - its connection pool - which it does not promise to keep. The
  async client is strict through `asyncio.timeout`.
- **No `wait(deadline, d)` helper** (spec 6): `time.sleep` and `asyncio.sleep` -
  which cancellation ends - are the language's waits, and Python code carries
  no deadline object to bound them by. `broadcast_with_retry` bounds its own
  waits by its timeout.
- **`rpc` is not offered**: it calls server API extensions, which Centrifugo
  does not provide.
- **`BoolValue` fields are `bool | None`.** `None` leaves the server's setting
  alone, which `False` cannot say.
- **An automatic batch always goes to `/api/batch`**, even with one command,
  and with `parallel: true`: its calls were made concurrently.
