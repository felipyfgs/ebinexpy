# Pesquisa do protocolo

Esta seção reúne a orientação editorial para evidências obtidas pela exploração
da traderoom. Capturas de rede só podem ser publicadas depois de sanitizadas;
email, senha, tokens, cookies e identificadores de conta nunca devem aparecer no
repositório.

## Fonte de verdade atual

A arquitetura resultante da exploração está registrada nos documentos
OpenSpec:

- [Proposta e escopo](../../openspec/changes/define-ebinexpy-core-library/proposal.md)
- [Design da biblioteca](../../openspec/changes/define-ebinexpy-core-library/design.md)
- [Lifecycle de cliente e sessão](../../openspec/changes/define-ebinexpy-core-library/specs/client-session-lifecycle/spec.md)
- [Acesso a dados de mercado](../../openspec/changes/define-ebinexpy-core-library/specs/market-data-access/spec.md)
- [Lifecycle de ordens OPTION](../../openspec/changes/define-ebinexpy-core-library/specs/option-order-lifecycle/spec.md)
- [Eventos tipados](../../openspec/changes/define-ebinexpy-core-library/specs/typed-event-dispatch/spec.md)
- [Transporte raw instável](../../openspec/changes/define-ebinexpy-core-library/specs/unstable-raw-transport/spec.md)

## Política para novos artefatos

Antes de adicionar um relatório, HAR, frame STOMP ou captura de tela:

1. confirme visualmente e no payload que a conta é `TEST`;
2. substitua credenciais, JWTs, cookies e IDs por marcadores neutros;
3. registre somente os campos necessários para documentar o contrato;
4. execute o scanner de segredos do projeto;
5. relacione a evidência a um teste ou decisão de design.

Resultados de execução pertencem à seção de [validação](../validation/index.md),
e não a esta seção.
