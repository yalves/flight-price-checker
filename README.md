# flight-price-checker

Acompanha o preco de passagens aereas Rio de Janeiro &rarr; Buenos Aires
(Aeroparque Jorge Newbery, AEP), ida **21/11/2026** e volta **28/11/2026**,
saindo tanto do Galeao (GIG) quanto do Santos Dumont (SDU).

Todo dia, um workflow do GitHub Actions abre um Chromium headless
(Playwright) e busca o preco em tres sites:

- **Google Flights**
- **Decolar.com**
- **LATAM**

A ida (aeroporto do Rio &rarr; Aeroparque) e a volta (Aeroparque &rarr;
aeroporto do Rio) sao buscadas separadamente, uma passagem so de ida de
cada vez, para que cada preco coletado fique claramente identificado como
"Ida" ou "Volta" — em vez de um preco unico de ida-e-volta somados.

O crawler coleta o **preco mais barato da rota** em cada busca. **Atencao
sobre bagagem:** esse preco NAO tem garantia de bagagem despachada. O
Google Flights (na pratica a unica fonte que responde — veja "Sobre falhas
de coleta") nao oferece filtro de bagagem despachada (so de bagagem de
mao) e nao diz no texto da pagina se a tarifa inclui bagagem — isso aparece
so como um icone por voo. Entao a tarifa mais barata pode ser uma tarifa
basica sem bagagem despachada (as vezes ate sem bagagem de mao). O
dashboard mostra um aviso claro sobre isso e, em cada linha, o link
"Ver oferta" para conferir a bagagem no proprio site antes de comprar.

Para nao pegar o preco errado, buscas ignoram linhas que tem preco mas nao
sao a tarifa da rota buscada — principalmente as sugestoes de outro
aeroporto (ex.: "Voos saindo de GIG por R$ 404" que aparece na busca do
SDU) e os avisos de historico de preco ("R$ X mais barato que o normal").
Sem esse cuidado, o preco de um aeroporto vizinho vazava como se fosse o da
rota.

So combinacoes site x aeroporto x trecho em que um preco foi realmente
encontrado viram linha em `precos_rio_buenosaires.csv`; uma busca que falha
(bloqueio do site, nenhum preco reconhecido, selector quebrado, etc.) fica
registrada so no log da execucao, sem gerar linha vazia no CSV ou no
dashboard. Cada linha guarda tambem o link de busca usado no site. Um
resumo em JSON e gravado em `docs/data.json`; uma pagina estatica em
`docs/index.html` le esse JSON e mostra um banner com o preco mais recente
de cada trecho (destacado quando esta ate R$ 600), graficos e uma tabela
com o historico de precos, publicada pelo GitHub Pages.

## Como roda

Tudo acontece no GitHub Actions (`.github/workflows/flight-price-crawler.yml`),
agendado para rodar uma vez por dia (08:00 horario de Brasilia). Nao depende
de nenhuma maquina pessoal ligada — o proprio runner do GitHub instala as
dependencias, executa o crawler e comita o CSV e o `docs/data.json`
atualizados de volta na branch `main`. Tambem da para disparar manualmente
pela aba **Actions** do repositorio, usando o botao "Run workflow".

## Publicar a pagina (passo manual, uma vez so)

A API do GitHub nao expoe esse toggle, entao e preciso configurar a mao:

1. **Settings &rarr; Pages**
2. Em **Build and deployment**, escolha **Source: Deploy from a branch**
3. Branch: **main**, pasta: **/docs**
4. Salvar

Depois disso a pagina fica em `https://yalves.github.io/flight-price-checker/`.

## Rodar localmente para testar

```bash
python -m venv .venv
source .venv/bin/activate  # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
python crawler.py
```

Isso grava/atualiza `precos_rio_buenosaires.csv` e `docs/data.json`. Para
so regenerar o JSON a partir de um CSV existente, sem abrir navegador:

```bash
python build_site_data.py
```

Para ver a pagina localmente, sirva a pasta `docs/`:

```bash
python -m http.server -d docs 8000
```

e abra `http://localhost:8000`.

No Windows, `run_daily.bat` faz a mesma coisa que `python crawler.py`,
preferindo o Python de dentro de `.venv\` se existir — util para agendar
no Agendador de Tarefas caso voce prefira rodar localmente em vez de
depender so do GitHub Actions.

## Ajustar rota, datas ou aeroportos

Tudo fica em `config.py`: `ORIGINS`, `DESTINATION`, `DEPART_DATE`,
`RETURN_DATE` e `ADULTS`. Depois de mudar, rode `python crawler.py` (ou
espere a proxima execucao agendada) para o dashboard refletir a nova busca.

## Por que a bagagem nao e filtrada (nota tecnica)

A ideia inicial era so contar tarifas com bagagem despachada, mas isso nao
e viavel com as fontes atuais:

- **Google Flights** nao tem filtro de bagagem despachada — so um filtro de
  bagagem de mao (`"Bagagens"` -> `"Adicionar bagagem de mao"`). A info de
  bagagem despachada por tarifa so aparece como icone/nos detalhes do voo,
  nao filtravel nem no texto da pagina (confirmado inspecionando os
  controles reais da pagina numa execucao).
- **Decolar e LATAM** ficam bloqueados por protecao anti-bot (veja abaixo),
  entao nao da pra ler bagagem la de qualquer jeito.

Por isso o crawler mostra o preco mais barato da rota com um aviso claro no
dashboard, em vez de esconder tudo. Se um dia voce quiser exigir pelo menos
bagagem de mao, da pra automatizar o filtro "Bagagens" do Google Flights
(clicar `"Bagagens"` e depois `"Adicionar bagagem de mao"` antes de ler os
precos).

O valor que destaca um preco no banner do site (hoje R$ 600) fica em
`docs/index.html`, na constante `LOW_PRICE_THRESHOLD_BRL`. As linhas
ignoradas na leitura de preco (sugestoes de outro aeroporto, historico)
ficam em `common.py`, na regex `_DECOY_LINE_RE`.

## Sobre falhas de coleta

**Decolar e LATAM tem protecao de bot forte** (paginas de bloqueio tipo
Akamai/PerimeterX) e, nos testes feitos ao montar este projeto, bloquearam
100% das buscas a partir do runner do GitHub Actions. Isso nao e algo que
o crawler tenta contornar (nao faz sentido, nem e o objetivo, burlar
protecao anti-bot de terceiros) — se esses sites continuarem bloqueando
sempre, o dashboard vai mostrar preco so do Google Flights mesmo, e essa e
uma limitacao conhecida, nao um bug.

Quando um site bloqueia ou nao mostra preco, essa busca especifica (site x
aeroporto x trecho) simplesmente nao gera linha nenhuma no CSV/dashboard —
ela nao aparece como um erro visivel na pagina, so fica registrada no log.
Isso e esperado ocasionalmente e nao trava a coleta dos outros
sites/trechos. Na pratica, hoje, so o Google Flights costuma responder;
Decolar e LATAM quase sempre bloqueiam a partir do runner do GitHub. Cada
execucao do workflow sobe um artefato chamado `crawler-logs` (aba
**Actions** -> a execucao -> Artifacts, disponivel por 14 dias) com
`crawler.log` e um screenshot de cada busca — o jeito mais direto de ver o
que a pagina realmente mostrou numa busca que deu `no_price_found`.

Para reduzir o caso de pegar um preco errado (um valor de um banner
promocional ou de uma tela ainda carregando, por exemplo), o crawler espera
ativamente ate aparecer um valor em R$ na pagina antes de ler o texto, em
vez de so esperar um tempo fixo.
