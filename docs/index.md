# ebinexpy documentation

`ebinexpy` is an asynchronous Python library for accessing Ebinex accounts,
market data, and orders.

## Installation

Install the latest release from [PyPI](https://pypi.org/project/ebinexpy/):

```bash
python3 -m pip install ebinexpy
```

The examples use `python3` on Linux and macOS; use `py` instead on Windows. The
version is optional. Use `ebinexpy==0.1.0` only when an application needs to
reproduce that exact release. To update an existing installation, run:

```bash
python3 -m pip install --upgrade ebinexpy
```

## Quick start

```python
import asyncio
import os

from ebinexpy import EbinexClient


async def main() -> None:
    async with EbinexClient(
        os.environ["EBINEX_EMAIL"],
        os.environ["EBINEX_PASSWORD"],
    ) as client:
        balance = await client.get_balance()
        print(balance.amount)


asyncio.run(main())
```

## Contents

- [Client methods](methods.md): connections, accounts, market data, streams, and orders.
- [Project README](../README.md): installation, sessions, and overview.
- [PyPI project](https://pypi.org/project/ebinexpy/): releases and distribution files.

## Important notes

- The library is asynchronous; its main methods must be called with
  `await`.
- The `TEST` account is selected by default.
- Operations on the `REAL` account require explicit authorization in the
  configuration.
- Access through `client.raw` is advanced and may change between versions.
