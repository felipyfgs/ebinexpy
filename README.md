# ebinexpy

`ebinexpy` é uma biblioteca Python assíncrona para controlar as capacidades
operacionais da traderoom Ebinex em robôs, workers e outros serviços. Ela não é
uma API HTTP, não executa estratégias e não depende do navegador em runtime.

O contrato atual é pre-alpha e suporta contas, perfil, saldo, mercado ao vivo e
histórico, além do ciclo de ordens `OPTION`. A conta `TEST` é sempre o padrão e
ordens em conta `REAL` ficam bloqueadas sem opt-in explícito.

## Instalação

```bash
pip install ebinexpy
```

Para desenvolvimento:

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

## Ciclo do cliente

```python
import asyncio
import os

from ebinexpy import EbinexClient


async def main() -> None:
    async with EbinexClient(os.environ["EBINEX_EMAIL"], os.environ["EBINEX_PASSWORD"]) as client:
        balance = await client.get_balance()
        assets = await client.list_assets()
        print(balance.amount, [asset.symbol for asset in assets if asset.tradable])


asyncio.run(main())
```

O construtor não abre conexões. `connect()` autentica, seleciona `TEST`, registra
os tópicos essenciais e só então marca o cliente como pronto. `disconnect()` é
idempotente e mantém a sessão; `logout()` desconecta e remove apenas a sessão da
identidade atual. O context manager fecha HTTP, WebSocket e handlers.

## Sessões

O padrão é `MemorySessionStore`. Para restaurar sessões entre processos, use um
arquivo privado:

```python
from pathlib import Path
from ebinexpy import ClientConfig, EbinexClient

config = ClientConfig.with_file_sessions(Path.home() / ".local/state/ebinexpy")
client = EbinexClient("email", "password", config)
```

O store usa chave derivada da identidade, diretório `0700`, arquivo `0600` e
replace atômico. A biblioteca não lê `.env`; carregue segredos no processo com
a ferramenta de configuração do seu serviço.

## Mercado e streams

Ativos e payouts vêm sempre de `configModes.OPTION`; a biblioteca não mantém
uma lista estática de ativos negociáveis. Datas de candles devem ter timezone.

```python
from ebinexpy import Timeframe

stream = await client.stream_candles("IDXUSDT", Timeframe.M1)
async with stream:
    async for event in stream:
        print(event.candle.close, event.snapshot)
```

Streams de candles, ticker e book têm filas limitadas e compartilham
subscriptions. Snapshots superseded podem ser coalescidos para impedir que um
consumer lento bloqueie o socket. Handlers registrados em `client.events`
também são executados sem bloquear o receive loop.

## Ordens OPTION

```python
from decimal import Decimal
from ebinexpy import Direction, OrderRequest, Timeframe

# Execute somente em uma conta TEST conscientemente selecionada.
request = OrderRequest(
    symbol="IDXUSDT",
    direction=Direction.CALL,
    investment=Decimal("1"),
    timeframe=Timeframe.M1,
    price=Decimal("2998.92"),  # preço atual observado no feed
)
order = await client.place_order(request)
settlement = await client.wait_order(order.id)
```

Somente a janela entre o envio e o recebimento do ID do broker é serializada;
ordens aceitas são acompanhadas independentemente. Falha ambígua de envio gera
`OrderSubmissionUnknownError` e nunca é repetida. Timeout de settlement gera
`SettlementTimeoutError.last_order`; timeout ou resultado desconhecido nunca é
convertido em derrota.

Para liberar conta REAL é necessário construir explicitamente
`ClientConfig(environment=AccountEnvironment.REAL, allow_real_trading=True)`.
O mesmo guard também protege `client.raw.send()` no destino de execução.

## Acesso raw e estabilidade

`client.raw.request`, `subscribe` e `send` reutilizam autenticação, TLS,
readiness, redaction e seleção de conta. O formato raw REST/STOMP é
deliberadamente instável e pode mudar entre versões pre-alpha. Requests HTTP
seguros podem reautenticar uma vez após 401; execução de ordem nunca tem replay
automático.

Veja [examples/read_market.py](examples/read_market.py) e o exemplo de ordem
DEMO com gate explícito em [examples/demo_order.py](examples/demo_order.py).
A matriz sanitizada da última execução está em
[docs/validation/demo-live-validation.md](docs/validation/demo-live-validation.md).
