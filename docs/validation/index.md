# Validação

A validação da `ebinexpy` combina testes determinísticos, fixtures sanitizadas e
uma suíte live que só executa quando habilitada explicitamente em conta DEMO.

## Evidências disponíveis

- [Relatório da validação live DEMO](demo-live-validation.md)
- [Como executar testes e verificações](../guides/development-testing.md)
- [Política da suíte live](../../tests/integration/demo/README.md)
- [Fixtures e testes de contrato](../../tests/contract/README.md)

## Níveis de validação

| Nível | Objetivo | Usa credenciais | Pode criar ordem |
| --- | --- | --- | --- |
| Unitário/contrato | Tipos, parsers, stores, concorrência e transportes | Não | Não |
| Live read-only | Autenticação, contas, mercado, streams e raw | Sim | Não |
| Live com ordem | Submissão e settlement completo em `TEST` | Sim | Uma, com gate adicional |

O CI executa somente verificações offline. Testes live exigem variáveis de
ambiente e nunca devem ser habilitados com credenciais de conta REAL.
