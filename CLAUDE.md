# CLAUDE.md

See [AGENTS.md](AGENTS.md). It is the guide for working on this package and
applies here in full: the layout, the invariants, how to run the suite, how to
update to a new Centrifugo API, and the list of things that look wrong but are
deliberate.

Three points from it are worth repeating, because they are the ones most easily
lost:

- **Never edit `cent/_api.py` or `cent/proxy/_types.py`.** Change `proto/` or
  `gen/`, then run `make generate`.
- **Every call raises unless it did everything asked.** A broadcast or batch in
  which some parts failed raises `BroadcastFailedChannelsError` or
  `BatchFailedCommandsError`, carrying every part's outcome.
- **`Client` and `AsyncClient` behave the same**: change both, test both.

Run `make check` before reporting a change as done, and `make test-integration`
with Centrifugo running for a change to the transport, errors, batching or
handlers.
