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

Um preco so conta se a oferta inclui bagagem despachada. Cada site confirma
isso de um jeito diferente (veja a secao abaixo): no Google Flights o
crawler usa o proprio filtro "Bagagens" do site, que refaz o preco exibido
ja somando 1 bagagem despachada; no Decolar/LATAM (quando acessiveis) o
texto da pagina precisa mencionar isso explicitamente perto do valor (ex.:
"bagagem despachada incluida") — um valor sem essa mencao por perto e
descartado, e um valor perto de "sem bagagem despachada"/"somente bagagem
de mao" tambem e descartado. So combinacoes site x aeroporto x
trecho em que um preco assim foi realmente encontrado viram linha em
`precos_rio_buenosaires.csv`; uma busca que falha (bloqueio do site,
nenhum preco com bagagem confirmada, selector quebrado, etc.) fica
registrada so no log da execucao, sem gerar linha vazia no CSV ou no
dashboard. Cada linha guarda tambem o link de busca usado no site, para ir
direto conferir/comprar a oferta. Um resumo em JSON e gravado em
`docs/data.json`; uma pagina estatica em `docs/index.html` le esse JSON e
mostra um banner com o preco mais recente de cada trecho (destacado
quando esta ate R$ 600), graficos e uma tabela com o historico de precos,
publicada pelo GitHub Pages.

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

## Ajustar a exigencia de bagagem ou o preco em destaque

- **Google Flights**: `sites/google_flights.py` clica no filtro "Bagagens"
  do proprio site e aumenta bagagem despachada para 1 antes de ler os
  precos (`_apply_checked_bag_filter`). Isso existe porque o Google Flights
  so indica bagagem incluida por icone ao lado do preco — o texto da pagina
  nunca menciona isso, entao um reconhecimento por palavra-chave nunca
  funcionaria ali (confirmado num screenshot real salvo em `logs/`). Se o
  Google mudar os rotulos do filtro e o clique parar de funcionar, o
  crawler cai automaticamente para a checagem por texto (que vai dar
  `no_price_found`, nunca um preco errado) — ajuste
  `_BAGGAGE_FILTER_BUTTON_LABELS` / `_CHECKED_BAG_INCREMENT_LABELS` /
  `_FILTER_DONE_LABELS` nesse arquivo se isso acontecer.
- **Decolar / LATAM**: palavras usadas para reconhecer "inclui bagagem
  despachada" e "sem bagagem despachada" ficam em `common.py`, nas listas
  `_CHECKED_BAG_INCLUDED_HINTS` e `_CHECKED_BAG_EXCLUDED_HINTS`. Os
  screenshots em `logs/` (ou no artefato `crawler-logs` de cada execucao,
  aba **Actions**) ajudam a ver o texto real da pagina numa execucao que
  deu `no_price_found`.
- O valor que destaca um preco no banner do site (hoje R$ 600) fica em
  `docs/index.html`, na constante `LOW_PRICE_THRESHOLD_BRL`.

## Sobre falhas de coleta

**Decolar e LATAM tem protecao de bot forte** (paginas de bloqueio tipo
Akamai/PerimeterX) e, nos testes feitos ao montar este projeto, bloquearam
100% das buscas a partir do runner do GitHub Actions. Isso nao e algo que
o crawler tenta contornar (nao faz sentido, nem e o objetivo, burlar
protecao anti-bot de terceiros) — se esses sites continuarem bloqueando
sempre, o dashboard vai mostrar preco so do Google Flights mesmo, e essa e
uma limitacao conhecida, nao um bug.

Alem disso, um preco so e aceito com bagagem despachada confirmada (veja
acima) — entao uma busca tambem pode nao gerar linha se o site respondeu
normalmente mas so tinha tarifa sem bagagem. Quando qualquer uma dessas
coisas acontece, essa busca especifica (site x aeroporto x trecho)
simplesmente nao gera linha nenhuma no CSV/dashboard — ela nao aparece
como um erro visivel na pagina, so fica registrada no log. Isso e esperado
ocasionalmente e nao trava a coleta dos outros sites/trechos. Cada
execucao do workflow sobe um artefato chamado `crawler-logs` (aba
**Actions** -> a execucao -> Artifacts, disponivel por 14 dias) com
`crawler.log` e um screenshot de cada busca — o jeito mais direto de ver o
que a pagina realmente mostrou numa busca que deu `no_price_found`.

Para reduzir o caso de pegar um preco errado (um valor de um banner
promocional ou de uma tela ainda carregando, por exemplo), o crawler espera
ativamente ate aparecer um valor em R$ na pagina antes de ler o texto, em
vez de so esperar um tempo fixo.
