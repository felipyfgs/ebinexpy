# Documentação da ebinexpy

`ebinexpy` é uma biblioteca Python assíncrona para integrar serviços à
traderoom Ebinex. A documentação está organizada por intenção: começar a usar,
consultar o contrato público ou entender as evidências de engenharia.

> **Estado do projeto:** pre-alpha. A conta `TEST` é o padrão. Operações em
> conta `REAL` exigem opt-in explícito e continuam sujeitas às proteções da
> biblioteca.

## Comece por aqui

- [Instalação e primeiro cliente](guides/installation-quickstart.md)
- [Ciclo de vida e sessões](guides/lifecycle-sessions.md)
- [Mercado e streams](guides/market-streams.md)
- [Ordens DEMO e segurança da conta REAL](guides/demo-orders-real-safety.md)
- [Índice de guias](guides/index.md)

## Referência da API

- [Cliente `EbinexClient`](api/client.md)
- [Configuração e autenticação](api/configuration-and-auth.md)
- [Contas](api/accounts.md)
- [Mercado](api/market.md)
- [Ordens](api/orders.md)
- [Eventos](api/events.md)
- [Acesso raw](api/raw.md)
- [Modelos](api/models.md)
- [Exceções](api/exceptions.md)
- [Índice da API](api/index.md)

## Engenharia e validação

- [Pesquisa do protocolo](research/index.md)
- [Validação](validation/index.md)
- [Validação live em conta DEMO](validation/demo-live-validation.md)
- [Desenvolvimento e testes](guides/development-testing.md)

## Documentos do projeto

- [README do repositório](../README.md)
- [Changelog](../CHANGELOG.md)
- [Proposta OpenSpec](../openspec/changes/define-ebinexpy-core-library/proposal.md)
- [Decisões de arquitetura](../openspec/changes/define-ebinexpy-core-library/design.md)

## Limites de uso

Esta é uma biblioteca não oficial. Consumidores devem observar os termos da
plataforma, proteger credenciais e validar suas integrações primeiro em conta
`TEST`. A documentação não recomenda automação financeira sem supervisão.
