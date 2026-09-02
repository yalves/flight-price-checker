# flight-price-checker

Acompanha o preco de passagens aereas Rio de Janeiro &rarr; Buenos Aires
(Aeroparque Jorge Newbery, AEP), ida **21/11/2026** e volta **28/11/2026**,
saindo tanto do Galeao (GIG) quanto do Santos Dumont (SDU).

Todo dia, um workflow do GitHub Actions abre um Chromium headless
(Playwright) e busca o preco em tres sites:

- **Google Flights**
- **Decolar.com**
- **LATAM**

O resultado de cada combinacao site x aeroporto de origem vira uma linha em
`precos_rio_buenosaires.csv`, e um resumo em JSON e gravado em
`docs/data.json`. Uma pagina estatica em `docs/index.html` le esse JSON e
mostra graficos e uma tabela com o historico de precos, publicada pelo
GitHub Pages.

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

## Sobre falhas de coleta

Google Flights, Decolar e LATAM usam protecao contra bots, e de vez em
quando um ou outro pode bloquear a requisicao ou mudar a estrutura da
pagina. Quando isso acontece, a linha correspondente no CSV/dashboard
aparece com `status=error` ou `status=no_price_found` em vez de um preco —
isso e esperado ocasionalmente e nao trava a coleta dos outros dois sites.
Se um site ficar falhando com frequencia, o log da execucao (aba **Actions**
do workflow, ou `logs/crawler.log` numa rodada local) costuma mostrar o
motivo, e as vezes um screenshot de depuracao em `logs/`.
