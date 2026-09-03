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

Um preco so conta se a oferta inclui bagagem despachada — o texto da pagina
precisa mencionar isso explicitamente perto do valor (ex.: "bagagem
despachada incluida"); um valor sem essa mencao por perto e descartado, e
um valor perto de uma mencao do tipo "sem bagagem despachada"/"somente
bagagem de mao" tambem e descartado. So combinacoes site x aeroporto x
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

- Palavras usadas para reconhecer "inclui bagagem despachada" e "sem
  bagagem despachada" ficam em `common.py`, nas listas
  `_CHECKED_BAG_INCLUDED_HINTS` e `_CHECKED_BAG_EXCLUDED_HINTS`. Isso e um
  reconhecimento por texto — se um site mudar a forma como anuncia bagagem
  (ou passar a so usar icone, sem texto), pode parar de aparecer resultado
  para ele ate a lista ser ajustada; os screenshots em `logs/` ajudam a ver
  o texto real da pagina numa execucao que deu `no_price_found`.
- O valor que destaca um preco no banner do site (hoje R$ 600) fica em
  `docs/index.html`, na constante `LOW_PRICE_THRESHOLD_BRL`.

## Sobre falhas de coleta

Google Flights, Decolar e LATAM usam protecao contra bots, e de vez em
quando um ou outro pode bloquear a requisicao ou mudar a estrutura da
pagina. Alem disso, agora um preco so e aceito com bagagem despachada
confirmada no texto da pagina (veja acima) — entao uma busca tambem pode
nao gerar linha se so encontrar tarifas sem bagagem, mesmo que o site
tenha respondido normalmente. Quando qualquer uma dessas coisas acontece,
essa busca especifica (site x aeroporto x trecho) simplesmente nao gera
linha nenhuma no CSV/dashboard — ela nao aparece como um erro visivel na
pagina, so fica registrada no log. Isso e esperado ocasionalmente e nao
trava a coleta dos outros sites/trechos. Se um site ficar falhando com
frequencia (poucas linhas novas aparecendo para ele ao longo dos dias), o
log da execucao (aba **Actions** do workflow, ou `logs/crawler.log` numa
rodada local) diz se foi por falta de preco, falta de bagagem confirmada
ou erro, e as vezes um screenshot de depuracao em `logs/` mostra o texto
real da pagina naquele momento.

Para reduzir o caso de pegar um preco errado (um valor de um banner
promocional ou de uma tela ainda carregando, por exemplo), o crawler espera
ativamente ate aparecer um valor em R$ na pagina antes de ler o texto, em
vez de so esperar um tempo fixo.
