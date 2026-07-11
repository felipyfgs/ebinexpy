# Validação live em conta DEMO

Este relatório registra a aceitação da superfície pública contra a traderoom
Ebinex em conta `TEST`. Nenhum segredo, token, cookie ou identificador de conta
é reproduzido aqui.

## Resultado

Quatro cenários live foram executados com sucesso:

1. superfície read-only de contas e mercado;
2. lifecycle, saldo e acesso raw;
3. reautenticação e restauração de sessão em arquivo;
4. uma ordem `OPTION` de stake mínima, habilitada por gate separado.

A ordem DEMO observada percorreu `PENDING → OPEN → WIN`. O teste aceita também
os demais estados terminais legítimos (`LOSE`, `REFUNDED` e `CANCELED`) e exige
reconciliação do resultado por REST. Timeout ou resposta desconhecida não são
convertidos em derrota.

## Matriz da superfície validada

| Capacidade | Evidência live |
| --- | --- |
| Login e seleção de conta | Sessão conectada com ambiente `TEST` confirmado |
| Contas, perfil e saldo | Listagem e leituras tipadas concluídas |
| Ativos e payout | Ativo negociável e timeframe `M1` consultados |
| Candles REST | Intervalo consultado e ordenação temporal verificada |
| Candles, ticker e book | Um evento de cada stream recebido via WebSocket |
| Horário do broker | Evento recebido e estado local atualizado |
| Histórico de ordens | Consulta REST concluída |
| Raw REST | `GET /parameters` retornou sucesso |
| Raw STOMP | Frame recebido no tópico de gráfico |
| Reconexão | Dois disconnects idempotentes seguidos de nova conexão |
| Reautenticação | Token inválido substituído após resposta não autorizada |
| Store em arquivo | Sessão restaurada por novo cliente e apagada no logout |
| Ordem OPTION | Stake mínima em `TEST`, settlement e saldo reconciliados |

## Gatilhos de segurança

A suíte está em
[`tests/integration/demo/test_live_demo.py`](../../tests/integration/demo/test_live_demo.py)
e permanece desabilitada por padrão.

Para executar apenas a superfície read-only:

```bash
EBINEXPY_RUN_LIVE=1 pytest tests/integration/demo -q
```

As credenciais são lidas de `EBINEX_EMAIL` e `EBINEX_PASSWORD`. A suíte não lê
nem documenta seus valores.

O cenário que cria exatamente uma ordem exige ainda:

```bash
EBINEXPY_RUN_LIVE=1 \
EBINEXPY_RUN_DEMO_ORDER=YES_ONE_DEMO_ORDER \
pytest tests/integration/demo/test_live_demo.py::test_live_demo_exactly_one_settlement -q
```

O segundo gate reduz o risco de uma execução acidental. Antes de habilitá-lo, é
obrigatório confirmar que a conta selecionada é `TEST` e que a stake configurada
é a mínima aceita pela plataforma.

## Limites

Não foram provocados estados dependentes do resultado de mercado nem falhas de
rede destrutivas. `LOSE`, `REFUNDED`, `CANCELED`, rejeição, timeout, submissão
ambígua e concorrência permanecem cobertos por testes offline determinísticos.
Conta REAL, depósitos, saques, KYC e fechamento antecipado não fazem parte desta
validação.
