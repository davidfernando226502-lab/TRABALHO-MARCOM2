# =============================================================================
# gera_dashboard.py — Etapa 2: MySQL → Dashboard HTML
# Projeto Integrador I — Introdução à Solução de Problemas com Dados
#
# Lê os dados de Chikungunya do MySQL e gera o arquivo dashboard.html
# com KPIs, tabela por UF e gráfico de barras (Chart.js via CDN).
# =============================================================================

import mysql.connector
from mysql.connector import Error
from datetime import datetime

# -----------------------------------------------------------------------------
# CONFIGURAÇÕES — mesmas do etl_carga.py
# -----------------------------------------------------------------------------
DB_CONFIG = {
    "host":     "localhost",
    "user":     "root",
    "password": "senha",        # ← altere para sua senha
    "database": "projeto_chikungunya",
}

OUTPUT_HTML = "output/dashboard.html"

# =============================================================================
# FUNÇÕES DE CONSULTA AO BANCO
# =============================================================================

def consultar(cursor, sql: str):
    """Executa uma query e retorna todos os resultados."""
    cursor.execute(sql)
    return cursor.fetchall()


def obter_dados(cursor):
    """
    Executa todas as queries necessárias para o dashboard.
    Retorna um dicionário com os dados organizados.
    """
    dados = {}

    # KPI 1 — Total de casos notificados
    r = consultar(cursor, "SELECT COUNT(*) FROM notificacoes_chikungunya;")
    dados["total_casos"] = r[0][0]

    # KPI 2 — Casos confirmados (classi_fin IN (5, 13) = confirmado clínico + laboratorial)
    r = consultar(cursor, """
        SELECT COUNT(*) FROM notificacoes_chikungunya
        WHERE classi_fin IN (5, 13);
    """)
    dados["confirmados"] = r[0][0]

    # KPI 3 — Casos hospitalizados
    r = consultar(cursor, """
        SELECT COUNT(*) FROM notificacoes_chikungunya
        WHERE hospitaliz = 1;
    """)
    dados["hospitalizados"] = r[0][0]

    # KPI 4 — Óbitos (evolucao = 2)
    r = consultar(cursor, """
        SELECT COUNT(*) FROM notificacoes_chikungunya
        WHERE evolucao = 2;
    """)
    dados["obitos"] = r[0][0]

    # Tabela: casos por UF (top 15)
    dados["por_uf"] = consultar(cursor, """
        SELECT
            COALESCE(uf_nome, CAST(sg_uf_not AS CHAR)) AS uf,
            COUNT(*)                                    AS casos,
            SUM(CASE WHEN classi_fin IN (5,13) THEN 1 ELSE 0 END) AS confirmados,
            SUM(CASE WHEN hospitaliz = 1 THEN 1 ELSE 0 END)       AS hospitalizados
        FROM notificacoes_chikungunya
        GROUP BY uf_nome, sg_uf_not
        ORDER BY casos DESC
        LIMIT 15;
    """)

    # Série temporal: casos por mês de notificação
    dados["por_mes"] = consultar(cursor, """
        SELECT
            DATE_FORMAT(dt_notific, '%Y-%m') AS mes,
            COUNT(*)                          AS casos
        FROM notificacoes_chikungunya
        WHERE dt_notific IS NOT NULL
        GROUP BY mes
        ORDER BY mes;
    """)

    # Distribuição por sexo
    dados["por_sexo"] = consultar(cursor, """
        SELECT cs_sexo, COUNT(*) AS total
        FROM notificacoes_chikungunya
        WHERE cs_sexo IN ('F','M','I')
        GROUP BY cs_sexo
        ORDER BY total DESC;
    """)

    # Prevalência dos 4 principais sintomas
    dados["sintomas"] = consultar(cursor, """
        SELECT 'Febre'     AS sintoma, SUM(CASE WHEN febre    = 1 THEN 1 ELSE 0 END) AS positivos FROM notificacoes_chikungunya
        UNION ALL
        SELECT 'Cefaleia',              SUM(CASE WHEN cefaleia = 1 THEN 1 ELSE 0 END) FROM notificacoes_chikungunya
        UNION ALL
        SELECT 'Artralgia',             SUM(CASE WHEN artralgia= 1 THEN 1 ELSE 0 END) FROM notificacoes_chikungunya
        UNION ALL
        SELECT 'Exantema',              SUM(CASE WHEN exantema = 1 THEN 1 ELSE 0 END) FROM notificacoes_chikungunya
        ORDER BY positivos DESC;
    """)

    return dados


# =============================================================================
# FUNÇÕES DE GERAÇÃO DO HTML
# =============================================================================

def formatar_numero(n):
    """Formata número com separadores de milhar (pt-BR)."""
    return f"{n:,}".replace(",", ".")


def pct(parte, total):
    """Calcula percentual com 1 casa decimal."""
    if total == 0:
        return "0,0"
    return f"{(parte / total * 100):.1f}".replace(".", ",")


def gerar_html(dados: dict) -> str:
    """Monta e retorna o HTML completo do dashboard."""

    # ---- KPIs ----
    total  = dados["total_casos"]
    conf   = dados["confirmados"]
    hosp   = dados["hospitalizados"]
    obit   = dados["obitos"]

    # ---- Tabela UF ----
    linhas_uf = ""
    for uf, casos, confirmados, hosp_uf in dados["por_uf"]:
        linhas_uf += f"""
            <tr>
                <td><strong>{uf or '—'}</strong></td>
                <td>{formatar_numero(casos)}</td>
                <td>{formatar_numero(confirmados)}</td>
                <td>{formatar_numero(hosp_uf)}</td>
            </tr>"""

    # ---- Dados para Chart.js: evolução mensal ----
    meses_label = [str(m[0]) for m in dados["por_mes"]]
    meses_valor = [m[1] for m in dados["por_mes"]]

    # ---- Dados para Chart.js: sintomas ----
    sint_label = [s[0] for s in dados["sintomas"]]
    sint_valor = [s[1] for s in dados["sintomas"]]

    # ---- Dados para Chart.js: sexo ----
    sexo_map = {"F": "Feminino", "M": "Masculino", "I": "Ignorado"}
    sexo_label = [sexo_map.get(str(s[0]), str(s[0])) for s in dados["por_sexo"]]
    sexo_valor = [s[1] for s in dados["por_sexo"]]

    data_extracao = datetime.now().strftime("%d/%m/%Y %H:%M")

    # ---- HTML ----
    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Painel Chikungunya Brasil — 2026</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    /* ---- Reset e Base ---- */
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Segoe UI', Arial, sans-serif;
      background: #f0f4f8;
      color: #1a2535;
    }}

    /* ---- Header ---- */
    header {{
      background: linear-gradient(135deg, #0d3b66 0%, #1a6b96 100%);
      color: #fff;
      padding: 28px 40px;
      box-shadow: 0 2px 8px rgba(0,0,0,.25);
    }}
    header h1 {{ font-size: 1.8rem; letter-spacing: .5px; }}
    header p  {{ font-size: .9rem; opacity: .8; margin-top: 4px; }}

    /* ---- Container ---- */
    .container {{ max-width: 1200px; margin: 0 auto; padding: 28px 20px; }}

    /* ---- KPI Cards ---- */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 20px;
      margin-bottom: 32px;
    }}
    .kpi-card {{
      background: #fff;
      border-radius: 10px;
      padding: 24px 28px;
      box-shadow: 0 1px 6px rgba(0,0,0,.08);
      border-top: 5px solid var(--cor);
    }}
    .kpi-card .label {{ font-size: .8rem; text-transform: uppercase; letter-spacing: 1px; color: #5a6a7e; }}
    .kpi-card .valor {{ font-size: 2.4rem; font-weight: 700; color: var(--cor); margin: 6px 0 2px; }}
    .kpi-card .sub   {{ font-size: .82rem; color: #7a8a9a; }}

    /* ---- Seção de gráficos ---- */
    .charts-grid {{
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 20px;
      margin-bottom: 32px;
    }}
    @media (max-width: 780px) {{ .charts-grid {{ grid-template-columns: 1fr; }} }}

    .card {{
      background: #fff;
      border-radius: 10px;
      padding: 24px;
      box-shadow: 0 1px 6px rgba(0,0,0,.08);
    }}
    .card h2 {{
      font-size: 1rem;
      color: #0d3b66;
      border-bottom: 2px solid #e0e8f0;
      padding-bottom: 10px;
      margin-bottom: 18px;
    }}

    /* ---- Tabela UF ---- */
    .table-wrap {{ overflow-x: auto; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: .9rem;
    }}
    thead th {{
      background: #0d3b66;
      color: #fff;
      padding: 10px 14px;
      text-align: left;
      font-weight: 600;
    }}
    tbody tr:nth-child(even) {{ background: #f7fafc; }}
    tbody td {{ padding: 9px 14px; border-bottom: 1px solid #e8eef4; }}
    tbody tr:hover {{ background: #e8f4fd; }}

    /* ---- Sintomas chart card (full width) ---- */
    .full-width {{ grid-column: 1 / -1; }}

    /* ---- Footer ---- */
    footer {{
      text-align: center;
      font-size: .78rem;
      color: #7a8a9a;
      padding: 20px;
      border-top: 1px solid #dde4ed;
      margin-top: 10px;
    }}
  </style>
</head>
<body>

<header>
  <h1>🦟 Painel Chikungunya — Brasil 2026</h1>
  <p>Fonte: SINAN / DATASUS — dados.gov.br &nbsp;|&nbsp; Extração: {data_extracao}</p>
</header>

<div class="container">

  <!-- ===== KPIs ===== -->
  <div class="kpi-grid">
    <div class="kpi-card" style="--cor:#e63946">
      <div class="label">Total Notificados</div>
      <div class="valor">{formatar_numero(total)}</div>
      <div class="sub">casos registrados em 2026</div>
    </div>
    <div class="kpi-card" style="--cor:#2a9d8f">
      <div class="label">Confirmados</div>
      <div class="valor">{formatar_numero(conf)}</div>
      <div class="sub">{pct(conf, total)}% do total notificado</div>
    </div>
    <div class="kpi-card" style="--cor:#f4a261">
      <div class="label">Hospitalizados</div>
      <div class="valor">{formatar_numero(hosp)}</div>
      <div class="sub">{pct(hosp, total)}% dos casos</div>
    </div>
    <div class="kpi-card" style="--cor:#6c757d">
      <div class="label">Óbitos</div>
      <div class="valor">{formatar_numero(obit)}</div>
      <div class="sub">letalidade: {pct(obit, total)}%</div>
    </div>
  </div>

  <!-- ===== Gráficos ===== -->
  <div class="charts-grid">

    <!-- Linha temporal -->
    <div class="card">
      <h2>📅 Casos por Mês de Notificação</h2>
      <canvas id="chartMensal" height="90"></canvas>
    </div>

    <!-- Distribuição por sexo -->
    <div class="card">
      <h2>👥 Distribuição por Sexo</h2>
      <canvas id="chartSexo" height="160"></canvas>
    </div>

    <!-- Sintomas (full width) -->
    <div class="card full-width">
      <h2>🩺 Prevalência dos Principais Sintomas</h2>
      <canvas id="chartSintomas" height="60"></canvas>
    </div>

  </div>

  <!-- ===== Tabela por UF ===== -->
  <div class="card">
    <h2>🗺️ Casos por Unidade Federativa (Top 15)</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>UF</th>
            <th>Notificados</th>
            <th>Confirmados</th>
            <th>Hospitalizados</th>
          </tr>
        </thead>
        <tbody>
          {linhas_uf}
        </tbody>
      </table>
    </div>
  </div>

</div><!-- /container -->

<footer>
  Painel gerado automaticamente por <strong>gera_dashboard.py</strong> &nbsp;|&nbsp;
  Dados: SINAN/DATASUS — <a href="https://dados.gov.br" target="_blank">dados.gov.br</a>
  &nbsp;|&nbsp; Projeto Integrador I — UniFAJ / UniMAX
</footer>

<!-- ===== Chart.js scripts ===== -->
<script>
  // --- Gráfico Mensal ---
  new Chart(document.getElementById('chartMensal'), {{
    type: 'bar',
    data: {{
      labels: {meses_label},
      datasets: [{{
        label: 'Casos notificados',
        data: {meses_valor},
        backgroundColor: 'rgba(26, 107, 150, 0.75)',
        borderColor:     'rgba(26, 107, 150, 1)',
        borderWidth: 1,
        borderRadius: 4,
      }}]
    }},
    options: {{
      responsive: true,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        y: {{ beginAtZero: true, ticks: {{ callback: v => v.toLocaleString('pt-BR') }} }}
      }}
    }}
  }});

  // --- Gráfico Sexo (Doughnut) ---
  new Chart(document.getElementById('chartSexo'), {{
    type: 'doughnut',
    data: {{
      labels: {sexo_label},
      datasets: [{{
        data: {sexo_valor},
        backgroundColor: ['#e63946','#1a6b96','#adb5bd'],
        borderWidth: 2,
      }}]
    }},
    options: {{
      responsive: true,
      plugins: {{
        legend: {{ position: 'bottom' }},
        tooltip: {{ callbacks: {{ label: ctx => ' ' + ctx.parsed.toLocaleString('pt-BR') }} }}
      }}
    }}
  }});

  // --- Gráfico Sintomas ---
  new Chart(document.getElementById('chartSintomas'), {{
    type: 'bar',
    data: {{
      labels: {sint_label},
      datasets: [{{
        label: 'Casos com sintoma',
        data: {sint_valor},
        backgroundColor: ['#e63946','#f4a261','#2a9d8f','#457b9d'],
        borderRadius: 5,
      }}]
    }},
    options: {{
      indexAxis: 'y',
      responsive: true,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ beginAtZero: true, ticks: {{ callback: v => v.toLocaleString('pt-BR') }} }}
      }}
    }}
  }});
</script>

</body>
</html>"""
    return html


# =============================================================================
# EXECUÇÃO PRINCIPAL
# =============================================================================

def main():
    print("=" * 60)
    print("  Dashboard — Chikungunya SINAN 2026")
    print("=" * 60)

    # Conectar ao banco
    try:
        conn   = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print(f"  [OK] Conectado ao banco '{DB_CONFIG['database']}'.")
    except Error as e:
        print(f"  [ERRO] Conexão: {e}")
        return

    # Consultar dados
    print("\n[1/2] Consultando dados no MySQL...")
    dados = obter_dados(cursor)
    print(f"  Total de casos lidos: {dados['total_casos']:,}")

    cursor.close()
    conn.close()

    # Gerar HTML
    print(f"\n[2/2] Gerando '{OUTPUT_HTML}'...")
    html = gerar_html(dados)
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  [OK] Dashboard salvo em: {OUTPUT_HTML}")
    print("\n  Abra o arquivo no seu navegador para visualizar.")
    print("=" * 60)


if __name__ == "__main__":
    main()
