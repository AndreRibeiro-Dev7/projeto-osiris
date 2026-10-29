# Auditoria das dependências Python

O job `dependency-audit` do GitHub Actions instala as dependências de produção e desenvolvimento
declaradas em `pyproject.toml` e consulta vulnerabilidades conhecidas pelo
[pip-audit da PyPA](https://github.com/pypa/pip-audit). A ferramenta fica em um
ambiente virtual separado: suas dependências não entram no inventário da aplicação.

O inventário contém as versões efetivamente instaladas e transitivas, além do pip
do ambiente de CI. O pacote local `projeto-osiris` é excluído dessa consulta porque
seu código é analisado e testado no próprio repositório. Nenhuma dependência externa
é excluída intencionalmente. O job não usa credenciais de produção nem inicia a API.

## Comportamento do CI

Cada push em `main` e cada pull request executa a auditoria. Vulnerabilidades
encontradas tornam o job vermelho. Erros de consulta ou pacotes que não puderam ser
auditados também impedem a aprovação, por meio de `--strict`.

O artefato `dependency-audit` guarda `dependency-requirements.txt`, com nomes e
versões, e `dependency-audit.json`, com os resultados. A publicação do artefato é
tentada mesmo quando a auditoria falha. Se a instalação ou a consulta não terminar,
a falta do relatório não deve ser interpretada como ausência de vulnerabilidades.

## Repetir localmente

Crie um ambiente separado para a ferramenta e instale `pip-audit==2.10.1` nele.
Com o ambiente da aplicação já instalado, gere o inventário e consulte a base:

```powershell
.\.venv-codex\Scripts\python.exe -m pip list --format=freeze --exclude projeto-osiris | Set-Content -Encoding utf8 .\work\installed-audit-requirements.txt
.\.venv-audit\Scripts\python.exe -m pip_audit --requirement .\work\installed-audit-requirements.txt --no-deps --disable-pip --strict --progress-spinner off --cache-dir .\work\audit-cache --format json --output .\work\installed-audit.json
```

A pasta `work` deve existir. O inventário local pode incluir ferramentas diferentes
das instaladas no CI. A consulta necessita de internet, mas não lê `.env` nem usa
contas da aplicação.

## Tratar resultados

Quando houver um achado, confira o identificador do aviso, o pacote, a versão
afetada e as versões corrigidas na fonte oficial. Atualize a dependência compatível,
execute os testes apropriados e repita a auditoria. Não descarte um aviso apenas
para deixar o CI verde; qualquer exceção exige justificativa e prazo de revisão.

Um resultado sem achados descreve apenas as versões e a base consultadas naquele
momento. Não verifica o código próprio, imagens do sistema operacional, JavaScript,
segredos ou falhas ainda não publicadas. As faixas atuais de versões permitem que
novas instalações selecionem versões diferentes; esta etapa não introduz um lockfile.

## Resultado desta revisão

O inventário local inicial tinha 92 pacotes externos. A base retornou 18 registros
de aviso em três pacotes: Black 25.12.0, pytest 8.4.2 e pip 25.0.1. Há registros
com identificadores repetidos; esse total não significa 18 falhas distintas.

As correções adotadas são:

- Black com mínimo 26.10.1 e limite abaixo de 27. O
  [aviso oficial](https://github.com/advisories/GHSA-cg8m-r9f2-5wm2) inclui um problema
  na GitHub Action do Black com `use_pyproject`, que o Osiris não utiliza. A
  atualização também supera as versões corrigidas dos demais avisos do pacote.
- pytest com mínimo 9.0.3 e limite abaixo de 10. O
  [changelog oficial](https://docs.pytest.org/en/stable/announce/release-9.0.3.html)
  registra a correção de diretório temporário inseguro, relevante para Linux.
- pip atualizado nos ambientes locais de aplicação e auditoria. O Docker já
  atualiza o pip durante o build; o novo job de auditoria também o faz.

A resolução nova das 76 dependências de produção não apresentou vulnerabilidades
conhecidas na consulta. Isso não inventaria o contêiner já publicado.

Após atualizar para Black 26.10.1, pytest 9.2.0 e pip 26.2.2, a nova auditoria
dos 92 pacotes externos locais terminou com código zero, sem vulnerabilidades
conhecidas e sem exclusões de avisos. Os relatórios locais estão na pasta ignorada
`work`, preservando o inventário anterior e o posterior para comparação.

Os 349 testes locais passaram com o novo pytest; 13 cenários dependentes de Linux
ou PostgreSQL ficaram pulados. Lint e tipos também passaram. O novo Black exigiu
somente a formatação de uma chamada na migração existente de proprietário principal;
essa alteração não muda o schema nem o conteúdo SQL da migração.

O job `dependency-audit` foi aprovado no
[CI do commit e63b845](https://github.com/AndreRibeiro-Dev7/projeto-osiris/actions/runs/40623521159),
sem vulnerabilidades conhecidas. O artefato com o inventário e o relatório foi
salvo nessa execução. Os outros três jobs também passaram.
