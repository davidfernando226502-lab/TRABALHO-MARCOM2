# =============================================================================
# etl_carga.py — Etapa 1: ETL CSV → MySQL
# Projeto Integrador I — Introdução à Solução de Problemas com Dados
#
# Dataset : SINAN — Chikungunya 2026 (dados.gov.br / DATASUS)
# Agravo  : A920 | Fonte: https://dados.gov.br/dados/conjuntos-dados/sinan-chikungunya
# Registros esperados: ~83.668
# =============================================================================

import csv
import mysql.connector
from mysql.connector import Error
from datetime import datetime

# -----------------------------------------------------------------------------
# CONFIGURAÇÕES — ajuste host/user/password conforme seu ambiente
# -----------------------------------------------------------------------------
DB_CONFIG = {
    "host":     "localhost",
    "user":     "root",
    "password": "senha",        # ← altere para sua senha
    "database": "projeto_chikungunya",
}

# Caminho do arquivo CSV baixado do SINAN
CSV_PATH = "dados/raw/CHIKBR26.csv"

# Codificação do arquivo (SINAN geralmente usa latin-1)
CSV_ENCODING = "latin-1"

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def parse_date(valor: str):
    """
    Converte string de data para objeto date.
    Aceita formatos: YYYY-MM-DD e YYYYMMDD.
    Retorna None se inválido ou vazio.
    """
    if not valor or valor.strip() == "":
        return None
    valor = valor.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(valor, fmt).date()
        except ValueError:
            continue
    return None  # não reconhecido


def parse_int(valor: str):
    """
    Converte string para inteiro.
    Retorna None se vazio ou inválido.
    """
    try:
        return int(float(valor.strip())) if valor and valor.strip() != "" else None
    except (ValueError, AttributeError):
        return None


def parse_str(valor: str, max_len: int = None):
    """
    Limpa e retorna string; trunca se necessário.
    Retorna None se vazio.
    """
    if valor is None:
        return None
    v = valor.strip()
    if v == "" or v.upper() in ("NA", "NAN", "NULL"):
        return None
    return v[:max_len] if max_len else v


# =============================================================================
# ETAPA 1 — CONECTAR AO BANCO E CRIAR ESTRUTURA
# =============================================================================

def criar_banco_e_tabelas(cursor):
    """
    Cria o banco de dados (se não existir) e as tabelas do projeto.
    Usa IF NOT EXISTS para ser seguro na segunda execução.
    """
    # Tabela principal: notificações de Chikungunya
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notificacoes_chikungunya (
            id             INT AUTO_INCREMENT PRIMARY KEY,
            tp_not         INT,
            id_agravo      VARCHAR(10),
            dt_notific     DATE,
            nu_ano         INT         NOT NULL,
            sg_uf_not      INT,
            uf_nome        VARCHAR(2),
            id_municip     INT,
            municipio      VARCHAR(100),
            dt_sin_pri     DATE,
            ano_nasc       INT,
            nu_idade_n     INT,
            cs_sexo        CHAR(1),
            cs_gestant     INT,
            cs_raca        INT,
            febre          INT,
            mialgia        INT,
            cefaleia       INT,
            exantema       INT,
            artralgia      INT,
            artrite        INT,
            vomito         INT,
            nausea         INT,
            hospitaliz     INT,
            dt_interna     DATE,
            classi_fin     INT,
            criterio       INT,
            evolucao       INT,
            dt_obito       DATE,
            dt_encerra     DATE,
            dt_digita      DATE
        ) ENGINE=InnoDB
          DEFAULT CHARSET=utf8mb4
          COMMENT='Notificações SINAN Chikungunya 2026 — fonte dados.gov.br';
    """)
    print("  [OK] Tabela 'notificacoes_chikungunya' criada/verificada.")


# =============================================================================
# ETAPA 2 — LER CSV E INSERIR NO BANCO (EXTRACT + TRANSFORM + LOAD)
# =============================================================================

# Mapeamento de código UF → sigla (IBGE)
UF_MAP = {
    11:"RO", 12:"AC", 13:"AM", 14:"RR", 15:"PA", 16:"AP", 17:"TO",
    21:"MA", 22:"PI", 23:"CE", 24:"RN", 25:"PB", 26:"PE", 27:"AL",
    28:"SE", 29:"BA", 31:"MG", 32:"ES", 33:"RJ", 35:"SP",
    41:"PR", 42:"SC", 43:"RS", 50:"MS", 51:"MT", 52:"GO", 53:"DF",
}

INSERT_SQL = """
    INSERT INTO notificacoes_chikungunya (
        tp_not, id_agravo, dt_notific, nu_ano, sg_uf_not, uf_nome,
        id_municip, municipio, dt_sin_pri, ano_nasc, nu_idade_n,
        cs_sexo, cs_gestant, cs_raca,
        febre, mialgia, cefaleia, exantema, artralgia, artrite,
        vomito, nausea, hospitaliz, dt_interna, classi_fin,
        criterio, evolucao, dt_obito, dt_encerra, dt_digita
    ) VALUES (
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s
    )
"""


def carregar_csv(cursor, conn):
    """
    Lê o CSV, transforma cada linha e inserta no MySQL em lotes de 500.
    """
    total_inseridos = 0
    total_erros     = 0
    lote            = []
    TAMANHO_LOTE    = 500

    with open(CSV_PATH, encoding=CSV_ENCODING, newline="") as f:

        # Detecta separador automaticamente (vírgula ou ponto-e-vírgula)
        amostra = f.read(4096)
        sep = ";" if amostra.count(";") > amostra.count(",") else ","
        f.seek(0)

        reader = csv.DictReader(f, delimiter=sep)

        for i, row in enumerate(reader, start=1):

            # --- TRANSFORM: limpar e tipar cada campo ---
            sg_uf  = parse_int(row.get("SG_UF_NOT", ""))
            uf_sig = UF_MAP.get(sg_uf, None)

            linha = (
                parse_int(row.get("TP_NOT")),
                parse_str(row.get("ID_AGRAVO"), 10),
                parse_date(row.get("DT_NOTIFIC")),
                parse_int(row.get("NU_ANO")) or 2026,   # NOT NULL, default 2026
                sg_uf,
                uf_sig,
                parse_int(row.get("ID_MUNICIP")),
                parse_str(row.get("MUNICIPIO"), 100),
                parse_date(row.get("DT_SIN_PRI")),
                parse_int(row.get("ANO_NASC")),
                parse_int(row.get("NU_IDADE_N")),
                parse_str(row.get("CS_SEXO"), 1),
                parse_int(row.get("CS_GESTANT")),
                parse_int(row.get("CS_RACA")),
                parse_int(row.get("FEBRE")),
                parse_int(row.get("MIALGIA")),
                parse_int(row.get("CEFALEIA")),
                parse_int(row.get("EXANTEMA")),
                parse_int(row.get("ARTRALGIA")),
                parse_int(row.get("ARTRITE")),
                parse_int(row.get("VOMITO")),
                parse_int(row.get("NAUSEA")),
                parse_int(row.get("HOSPITALIZ")),
                parse_date(row.get("DT_INTERNA")),
                parse_int(row.get("CLASSI_FIN")),
                parse_int(row.get("CRITERIO")),
                parse_int(row.get("EVOLUCAO")),
                parse_date(row.get("DT_OBITO")),
                parse_date(row.get("DT_ENCERRA")),
                parse_date(row.get("DT_DIGITA")),
            )
            lote.append(linha)

            # --- LOAD: inserir em lotes para eficiência ---
            if len(lote) >= TAMANHO_LOTE:
                try:
                    cursor.executemany(INSERT_SQL, lote)
                    conn.commit()
                    total_inseridos += len(lote)
                    print(f"  Inseridos: {total_inseridos:,} registros...", end="\r")
                except Error as e:
                    print(f"\n  [ERRO] Lote {i//TAMANHO_LOTE}: {e}")
                    total_erros += len(lote)
                    conn.rollback()
                lote = []

        # Inserir sobra do último lote
        if lote:
            try:
                cursor.executemany(INSERT_SQL, lote)
                conn.commit()
                total_inseridos += len(lote)
            except Error as e:
                print(f"\n  [ERRO] Último lote: {e}")
                total_erros += len(lote)
                conn.rollback()

    return total_inseridos, total_erros


# =============================================================================
# EXECUÇÃO PRINCIPAL
# =============================================================================

def main():
    print("=" * 60)
    print("  ETL — Chikungunya SINAN 2026")
    print("=" * 60)

    # Conectar sem database para poder criar se necessário
    try:
        conn_init = mysql.connector.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
        )
        cur_init = conn_init.cursor()
        cur_init.execute(
            f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']} "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )
        conn_init.commit()
        cur_init.close()
        conn_init.close()
        print(f"  [OK] Banco '{DB_CONFIG['database']}' verificado/criado.")
    except Error as e:
        print(f"  [ERRO] Não foi possível criar o banco: {e}")
        return

    # Conectar ao banco do projeto
    try:
        conn   = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print(f"  [OK] Conectado ao MySQL em '{DB_CONFIG['host']}'.")
    except Error as e:
        print(f"  [ERRO] Conexão falhou: {e}")
        return

    # Criar tabelas (DDL)
    print("\n[1/3] Criando estrutura do banco...")
    criar_banco_e_tabelas(cursor)

    # Carregar CSV (ETL)
    print(f"\n[2/3] Lendo '{CSV_PATH}' e inserindo no banco...")
    inseridos, erros = carregar_csv(cursor, conn)

    # Validação final
    print(f"\n[3/3] Validação:")
    cursor.execute("SELECT COUNT(*) FROM notificacoes_chikungunya;")
    contagem = cursor.fetchone()[0]
    print(f"  Registros inseridos : {inseridos:>10,}")
    print(f"  Erros               : {erros:>10,}")
    print(f"  SELECT COUNT(*)     : {contagem:>10,}")

    cursor.close()
    conn.close()
    print("\n  [CONCLUÍDO] ETL finalizado com sucesso!")
    print("=" * 60)


if __name__ == "__main__":
    main()
