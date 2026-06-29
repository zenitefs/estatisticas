import streamlit as st
import psycopg2  # Alterado de pyodbc para psycopg2
import pandas as pd
import datetime

st.set_page_config(page_title="Zenite FS - Sistema de Gestão", layout="wide")

if 'precisa_confirmar_duplicado' not in st.session_state:
    st.session_state.precisa_confirmar_duplicado = False

# ==============================================================================
# FUNÇÃO DE CONEXÃO AO BANCO DE DADOS (Configurada para PostgreSQL)
# ==============================================================================
def obter_conexao():
    # Caso vá hospedar na nuvem (Supabase/Neon), substitua pelos dados fornecidos por eles
    return psycopg2.connect(
        host="localhost",
        database="db_zenite",
        user="postgres",
        password="SUA_SENHA_AQUI",
        port="5432"
    )

# ==============================================================================
# FUNÇÕES DE LEITURA E VERIFICAÇÃO NATIVAS
# ==============================================================================
def carregar_dataframe(query, parametros=None):
    with obter_conexao() as conn:
        with conn.cursor() as cursor:
            if parametros:
                cursor.execute(query, parametros)
            else:
                cursor.execute(query)
            colunas = [col[0] for col in cursor.description]
            linhas = [list(row) for row in cursor.fetchall()]
            return pd.DataFrame(linhas, columns=colunas)

def listar_competicoes():
    return carregar_dataframe("SELECT id_competicao, nome FROM competicao ORDER BY nome")

def listar_adversarios():
    return carregar_dataframe("SELECT id_adversario, nome FROM adversario ORDER BY nome")

def listar_jogadores():
    return carregar_dataframe("SELECT id_jogador, nome FROM jogador ORDER BY nome")

def verificar_data_existente(data_str):
    with obter_conexao() as conn:
        with conn.cursor() as cursor:
            # Trocado ? por %s
            cursor.execute("SELECT COUNT(*) FROM partida WHERE data_partida = %s", (data_str,))
            return cursor.fetchone()[0] > 0  # Trocado fetchval() por fetchone()[0]

# ==============================================================================
# SUB-ROTINA DE SALVAMENTO DE PARTIDA
# ==============================================================================
def executar_salvamento_partida(data_jogo, id_comp_final, fase_jogo, local_jogo, id_adv_final, gols_pro, gols_contra, p_pro, p_contra, wo_val, dados_finais_jogadores, dict_jogadores):
    try:
        with obter_conexao() as conn:
            with conn.cursor() as cursor:
                
                # Adaptado para a sintaxe RETURNING do PostgreSQL e placeholders %s
                query_partida = """
                INSERT INTO partida (data_partida, id_competicao, fase, local, id_adversario, gols_pro, gols_contra, penaltis_pro, penaltis_contra, houve_wo, id_tecnico)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
                RETURNING id_partida;
                """
                cursor.execute(query_partida, (data_jogo.strftime('%Y-%m-%d'), id_comp_final, fase_jogo, local_jogo, id_adv_final, gols_pro, gols_contra, p_pro, p_contra, wo_val))
                id_partida_gerado = cursor.fetchone()[0] # Trocado fetchval() por fetchone()[0]
                
                if dados_finais_jogadores is not None:
                    for index, row in dados_finais_jogadores.iterrows():
                        nome_atleta = row['Jogador']
                        id_atleta = dict_jogadores[nome_atleta]
                        gols = int(row['Gols Marcados'])
                        amarelo = int(row['Cartão Amarelo'])
                        vermelho = int(row['Cartão Vermelho'])
                        
                        # Presença (Uso de %s)
                        cursor.execute("INSERT INTO participacao_jogador (id_partida, id_jogador) VALUES (%s, %s)", (id_partida_gerado, id_atleta))
                        
                        # Eventos (Uso de %s)
                        if gols > 0:
                            cursor.execute("INSERT INTO evento_jogador (id_partida, id_jogador, tipo_evento, quantidade) VALUES (%s, %s, 'GOL', %s)", (id_partida_gerado, id_atleta, gols))
                        if amarelo > 0:
                            cursor.execute("INSERT INTO evento_jogador (id_partida, id_jogador, tipo_evento, quantidade) VALUES (%s, %s, 'AMARELO', %s)", (id_partida_gerado, id_atleta, amarelo))
                        if vermelho > 0:
                            cursor.execute("INSERT INTO evento_jogador (id_partida, id_jogador, tipo_evento, quantidade) VALUES (%s, %s, 'VERMELHO', %s)", (id_partida_gerado, id_atleta, vermelho))
                
                conn.commit()
                
                st.session_state.mensagem_sucesso_partida = f"Partida salva com sucesso! ID Gerado: {id_partida_gerado}"
                st.session_state.lancar_baloes = True
                
                chaves_partida = ["input_data_jogo", "input_local", "input_fase", "input_gols_pro", "input_gols_contra", "input_wo", "input_penaltis_pro", "input_usar_penaltis", "input_penaltis_contra", "input_jogadores"]
                for c in chaves_partida:
                    if c in st.session_state: del st.session_state[c]
                
                st.rerun()
    except Exception as e:
        st.error(f"Erro crítico ao salvar no banco de dados: {e}")

# ==============================================================================
# CORPO PRINCIPAL DO SISTEMA
# ==============================================================================
st.title("⚽ Estatísticas Zenite FS")

df_comp = listar_competicoes()
df_adv = listar_adversarios()
df_jog = listar_jogadores()

list_comp_nomes = df_comp['nome'].tolist() if not df_comp.empty else []
list_adv_nomes = df_adv['nome'].tolist() if not df_adv.empty else []
list_jog_nomes = df_jog['nome'].tolist() if not df_jog.empty else []

dict_comp = dict(zip(df_comp['nome'], df_comp['id_competicao'])) if not df_comp.empty else {}
dict_adv = dict(zip(df_adv['nome'], df_adv['id_adversario'])) if not df_adv.empty else {}
dict_jogadores = dict(zip(df_jog['nome'], df_jog['id_jogador'])) if not df_jog.empty else {}

aba_partida, aba_cadastros, aba_est_equipe, aba_est_jogador = st.tabs(["📝 Registar Nova Partida", "➕ Gerir Cadastros (Novas Entidades)", "📊 Estatísticas da Equipe", "🏃 Estatísticas dos Jogadores"])

# ABA 1: REGISTAR NOVA PARTIDA
with aba_partida:
    if 'mensagem_sucesso_partida' in st.session_state:
        st.success(st.session_state.mensagem_sucesso_partida)
        if st.session_state.get('lancar_baloes'):
            st.balloons()
            st.session_state.lancar_baloes = False
        del st.session_state.mensagem_sucesso_partida

    st.header("Dados Gerais da Partida")
    col1, col2, col3, col4 = st.columns(4)
    with col1: data_jogo = st.date_input("Data da Partida", datetime.date.today(), key="input_data_jogo")
    with col2: local_jogo = st.text_input("Local", "Playball Pompeia", key="input_local")
    with col3: comp_selecionada = st.selectbox("Competição", list_comp_nomes, key="input_comp")
    with col4: fase_jogo = st.text_input("Fase do Torneio", "Fase de Grupos", key="input_fase")

    col5, col6, col7 = st.columns(3)
    with col5: adv_selecionado = st.selectbox("Adversário", list_adv_nomes, key="input_adv")
    with col6: gols_pro = st.number_input("Gols ZENITE", min_value=0, step=1, value=0, key="input_gols_pro")
    with col7: gols_contra = st.number_input("Gols Adversário", min_value=0, step=1, value=0, key="input_gols_contra")

    with st.expander("Configurações Avançadas (Disputa de Pênaltis / WO)"):
        col_wo, col_p1, col_p2 = st.columns(3)
        with col_wo: houve_wo = st.checkbox("A partida foi decidida por WO?", key="input_wo")
        with col_p1:
            penaltis_pro = st.number_input("Pênaltis Marcados por Zenite (se houver)", min_value=0, step=1, value=0, key="input_penaltis_pro")
            usar_penaltis = st.checkbox("Houve disputa de pênaltis?", key="input_usar_penaltis")
        with col_p2: penaltis_contra = st.number_input("Pênaltis Marcados pelo Rival (se houver)", min_value=0, step=1, value=0, key="input_penaltis_contra")

    st.markdown("---")
    st.header("🏃 Elenco e Estatísticas dos Jogadores")
    jogadores_convocados = st.multiselect("Selecione todos os jogadores que participaram na partida:", list_jog_nomes, key="input_jogadores")
    
    dados_finais_jogadores = None
    if jogadores_convocados:
        st.subheader("Insira os Gols e Cartões do Jogo:")
        df_temp_stats = pd.DataFrame({"Jogador": jogadores_convocados, "Gols Marcados": [0] * len(jogadores_convocados), "Cartão Amarelo": [0] * len(jogadores_convocados), "Cartão Vermelho": [0] * len(jogadores_convocados)})
        dados_finais_jogadores = st.data_editor(df_temp_stats, hide_index=True, use_container_width=True)

    id_comp_final = dict_comp.get(comp_selecionada)
    id_adv_final = dict_adv.get(adv_selecionado)
    p_pro = penaltis_pro if usar_penaltis else None
    p_contra = penaltis_contra if usar_penaltis else None
    
    # Tratando o booleano do Postgres para o campo WO
    wo_val = True if houve_wo else False

    if not st.session_state.precisa_confirmar_duplicado:
        if st.button("💾 SALVAR PARTIDA NO BANCO", type="primary"):
            if not houve_wo and not jogadores_convocados:
                st.error("Erro: Não pode registrar uma partida sem selecionar pelo menos um jogador participante (A não ser em caso de WO).")
            elif not comp_selecionada or not adv_selecionado:
                st.error("Erro: Selecione uma Competição e um Adversário válidos antes de salvar.")
            else:
                if verificar_data_existente(data_jogo.strftime('%Y-%m-%d')):
                    st.session_state.precisa_confirmar_duplicado = True
                    st.rerun()
                else:
                    executar_salvamento_partida(data_jogo, id_comp_final, fase_jogo, local_jogo, id_adv_final, gols_pro, gols_contra, p_pro, p_contra, wo_val, dados_finais_jogadores, dict_jogadores)
    else:
        st.warning(f"⚠️ Atenção: Já existe uma partida cadastrada no banco de dados na data {data_jogo.strftime('%d/%m/%Y')}.")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("👍 Sim, salvar partida duplicada", type="primary"):
                st.session_state.precisa_confirmar_duplicado = False
                executar_salvamento_partida(data_jogo, id_comp_final, fase_jogo, local_jogo, id_adv_final, gols_pro, gols_contra, p_pro, p_contra, wo_val, dados_finais_jogadores, dict_jogadores)
        with col_c2:
            if st.button("❌ Cancelar Operação"):
                st.session_state.precisa_confirmar_duplicado = False
                st.rerun()

# ABA 2: GERIR CADASTROS
with aba_cadastros:
    if 'mensagem_sucesso_cadastro' in st.session_state:
        st.success(st.session_state.mensagem_sucesso_cadastro)
        del st.session_state.mensagem_sucesso_cadastro

    st.header("Cadastrar Novas Entidades")
    sub_col1, sub_col2, sub_col3 = st.columns(3)
    
    with sub_col1:
        st.subheader("Nova Competição")
        nova_comp = st.text_input("Nome da Competição", key="input_nova_comp")
        if st.button("Adicionar Competição"):
            if nova_comp.strip() != "":
                try:
                    with obter_conexao() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute("INSERT INTO competicao (nome) VALUES (%s)", (nova_comp.strip(),))
                        conn.commit()
                    st.session_state.mensagem_sucesso_cadastro = f"Competição '{nova_comp.strip()}' adicionada com sucesso!"
                    if "input_nova_comp" in st.session_state: del st.session_state["input_nova_comp"]
                    st.rerun() 
                except Exception as e: st.error(f"Erro: {e}")

    with sub_col2:
        st.subheader("Novo Adversário")
        novo_adv = st.text_input("Nome do Adversário", key="input_novo_adv")
        if st.button("Adicionar Adversário"):
            if novo_adv.strip() != "":
                try:
                    with obter_conexao() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute("INSERT INTO adversario (nome) VALUES (%s)", (novo_adv.strip(),))
                        conn.commit()
                    st.session_state.mensagem_sucesso_cadastro = f"Adversário '{novo_adv.strip()}' adicionado com sucesso!"
                    if "input_novo_adv" in st.session_state: del st.session_state["input_novo_adv"]
                    st.rerun()
                except Exception as e: st.error(f"Erro: {e}")

    with sub_col3:
        st.subheader("Novo Atleta / Jogador")
        novo_jog = st.text_input("Nome do Jogador", key="input_novo_jog")
        posicao_jog = st.selectbox("Posição (Opcional)", ["Não Definida", "Goleiro", "Fixo", "Ala Direita", "Ala Esquerda", "Pivô"], key="input_posicao_jog")
        if st.button("Adicionar Jogador"):
            if novo_jog.strip() != "":
                try:
                    with obter_conexao() as conn:
                        with conn.cursor() as cursor:
                            cursor.execute("INSERT INTO jogador (nome, posicao) VALUES (%s, %s)", (novo_jog.strip(), posicao_jog))
                        conn.commit()
                    st.session_state.mensagem_sucesso_cadastro = f"Atleta '{novo_jog.strip()}' cadastrado com sucesso!"
                    if "input_novo_jog" in st.session_state: del st.session_state["input_novo_jog"]
                    if "input_posicao_jog" in st.session_state: del st.session_state["input_posicao_jog"]
                    st.rerun()
                except Exception as e: st.error(f"Erro: {e}")

# ABA 3: ESTATÍSTICAS DA EQUIPE
with aba_est_equipe:
    st.header("📊 Painel de Performance Analítica da Equipe")
    
    # Alterado YEAR(p.data_partida) para EXTRACT(YEAR FROM p.data_partida)
    q_partidas_geral = """
    SELECT p.id_partida, p.data_partida, EXTRACT(YEAR FROM p.data_partida)::int as ano,
           c.nome as nome_competicao, p.fase, p.local,
           a.nome as nome_adversario, p.gols_pro, p.gols_contra,
           p.penaltis_pro, p.penaltis_contra, p.houve_wo
    FROM partida p
    LEFT JOIN competicao c ON p.id_competicao = c.id_competicao
    LEFT JOIN adversario a ON p.id_adversario = a.id_adversario
    """
    df_p_geral = carregar_dataframe(q_partidas_geral)
    df_e_geral = carregar_dataframe("SELECT id_partida, tipo_evento, quantidade FROM evento_jogador")
    
    if df_p_geral.empty:
        st.info("Nenhuma partida registrada para gerar estatísticas.")
    else:
        win_c = (df_p_geral['gols_pro'] > df_p_geral['gols_contra']) | ((df_p_geral['gols_pro'] == df_p_geral['gols_contra']) & (df_p_geral['penaltis_pro'] > df_p_geral['penaltis_contra']))
        loss_c = (df_p_geral['gols_contra'] > df_p_geral['gols_pro']) | ((df_p_geral['gols_pro'] == df_p_geral['gols_contra']) & (df_p_geral['penaltis_contra'] > df_p_geral['penaltis_pro']))
        draw_c = (df_p_geral['gols_pro'] == df_p_geral['gols_contra']) & (df_p_geral['penaltis_pro'].isna() | (df_p_geral['penaltis_pro'] == df_p_geral['penaltis_contra']))
        
        df_p_geral['V'] = win_c.astype(int)
        df_p_geral['D'] = loss_c.astype(int)
        df_p_geral['E'] = draw_c.astype(int)
        
        anos_disponiveis = ["Todos"] + sorted(df_p_geral['ano'].dropna().unique().tolist(), reverse=True)
        ano_equipe_sel = st.selectbox("Filtrar Visão por Ano/Temporada:", anos_disponiveis, key="filtro_ano_equipe")
        
        df_p_eq_filtrado = df_p_geral.copy()
        if ano_equipe_sel != "Todos":
            df_p_eq_filtrado = df_p_eq_filtrado[df_p_eq_filtrado['ano'] == int(ano_equipe_sel)]
            
        total_p = len(df_p_eq_filtrado)
        total_v = int(df_p_eq_filtrado['V'].sum())
        total_e = int(df_p_eq_filtrado['E'].sum())
        total_d = int(df_p_eq_filtrado['D'].sum())
        total_gp = int(df_p_eq_filtrado['gols_pro'].sum())
        total_gc = int(df_p_eq_filtrado['gols_contra'].sum())
        saldo_g = total_gp - total_gc
        aprov_eq = round(((total_v * 3 + total_e) / (total_p * 3) * 100), 1) if total_p > 0 else 0.0
        
        match_ids_eq = df_p_eq_filtrado['id_partida'].tolist()
        df_e_eq_filtrado = df_e_geral[df_e_geral['id_partida'].isin(match_ids_eq)]
        total_amarelos = int(df_e_eq_filtrado[df_e_eq_filtrado['tipo_evento'] == 'AMARELO']['quantidade'].sum())
        total_vermelhos = int(df_e_eq_filtrado[df_e_eq_filtrado['tipo_evento'] == 'VERMELHO']['quantidade'].sum())
        
        st.markdown("### 📋 Totais Gerais Acumulados")
        m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
        m_col1.metric("Partidas", total_p)
        m_col2.metric("Vitórias", total_v)
        m_col3.metric("Empates", total_e)
        m_col4.metric("Derrotas", total_d)
        m_col5.metric("Aproveitamento (%)", f"{aprov_eq}%")
        
        m_col6, m_col7, m_col8, m_col9, m_col10 = st.columns(5)
        m_col6.metric("Gols Pró", total_gp)
        m_col7.metric("Gols Contra", total_gc)
        m_col8.metric("Saldo de Gols", saldo_g)
        m_col9.metric("Amarelos", total_amarelos)
        m_col10.metric("Vermelhos", total_vermelhos)
        
        st.markdown("---")
        st.subheader("🏆 Estatísticas Agrupadas por Torneio (Competição)")
        if total_p > 0:
            df_g_torneio = df_p_eq_filtrado.groupby('nome_competicao').agg(Partidas=('id_partida', 'count'), Vitórias=('V', 'sum'), Empates=('E', 'sum'), Derrotas=('D', 'sum'), Gols_Marcados=('gols_pro', 'sum'), Gols_Sofridos=('gols_contra', 'sum')).reset_index()
            df_g_torneio['Saldo'] = df_g_torneio['Gols_Marcados'] - df_g_torneio['Gols_Sofridos']
            df_g_torneio['Aproveitamento (%)'] = ((df_g_torneio['Vitórias'] * 3 + df_g_torneio['Empates']) / (df_g_torneio['Partidas'] * 3) * 100).round(1)
            st.dataframe(df_g_torneio.rename(columns={'nome_competicao': 'Competição'}), hide_index=True, use_container_width=True)
            
        st.subheader("⚔️ Estatísticas Agrupadas por Adversário")
        if total_p > 0:
            df_g_adv = df_p_eq_filtrado.groupby('nome_adversario').agg(Partidas=('id_partida', 'count'), Vitórias=('V', 'sum'), Empates=('E', 'sum'), Derrotas=('D', 'sum'), Gols_Marcados=('gols_pro', 'sum'), Gols_Sofridos=('gols_contra', 'sum')).reset_index()
            df_g_adv['Saldo'] = df_g_adv['Gols_Marcados'] - df_g_adv['Gols_Sofridos']
            df_g_adv['Aproveitamento (%)'] = ((df_g_adv['Vitórias'] * 3 + df_g_adv['Empates']) / (df_g_adv['Partidas'] * 3) * 100).round(1)
            st.dataframe(df_g_adv.rename(columns={'nome_adversario': 'Adversário'}), hide_index=True, use_container_width=True)

# ABA 4: ESTATÍSTICAS DOS JOGADORES
with aba_est_jogador:
    st.header("🏃 Painel de Desempenho por Jogador")
    
    df_part_j = carregar_dataframe("SELECT pj.id_partida, pj.id_jogador, j.nome as nome_jogador FROM participacao_jogador pj JOIN jogador j ON pj.id_jogador = j.id_jogador")
    df_ev_j = carregar_dataframe("SELECT id_partida, id_jogador, tipo_evento, quantidade FROM evento_jogador")
    
    if df_p_geral.empty or df_jog.empty:
        st.info("Cadastre dados suficientes para gerar relatórios individuais.")
    else:
        lista_atlet_box = sorted(df_jog['nome'].tolist())
        jog_perfil_sel = st.selectbox("Selecione o Atleta para Análise:", lista_atlet_box, key="perfil_jog_stats")
        id_jog_perfil = dict_jogadores[jog_perfil_sel]
        
        ids_partidas_do_atleta = df_part_j[df_part_j['id_jogador'] == id_jog_perfil]['id_partida'].tolist()
        df_p_atleta_base = df_p_geral[df_p_geral['id_partida'].isin(ids_partidas_do_atleta)].copy()
        
        st.markdown("#### 🔍 Filtros Avançados de Confronto")
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            anos_atleta = ["Todos"] + sorted(df_p_atleta_base['ano'].dropna().unique().tolist(), reverse=True)
            f_ano_j = st.selectbox("Temporada / Ano", anos_atleta, key="f_j_ano")
        with f_col2:
            comp_atleta = ["Todos"] + sorted(df_p_atleta_base['nome_competicao'].dropna().unique().tolist())
            f_comp_j = st.selectbox("Competição", comp_atleta, key="f_j_comp")
        with f_col3:
            adv_atleta = ["Todos"] + sorted(df_p_atleta_base['nome_adversario'].dropna().unique().tolist())
            f_adv_j = st.selectbox("Adversário Enfrentado", adv_atleta, key="f_j_adv")
            
        f_col4, f_col5 = st.columns(2)
        with f_col4:
            local_atleta = ["Todos"] + sorted(df_p_atleta_base['local'].dropna().unique().tolist())
            f_loc_j = st.selectbox("Local / Pavilhão", local_atleta, key="f_j_local")
        with f_col5:
            fase_atleta = ["Todos"] + sorted(df_p_atleta_base['fase'].dropna().unique().tolist())
            f_fase_j = st.selectbox("Fase da Competição", fase_atleta, key="f_j_fase")
            
        df_p_j_final = df_p_atleta_base.copy()
        if f_ano_j != "Todos": df_p_j_final = df_p_j_final[df_p_j_final['ano'] == int(f_ano_j)]
        if f_comp_j != "Todos": df_p_j_final = df_p_j_final[df_p_j_final['nome_competicao'] == f_comp_j]
        if f_adv_j != "Todos": df_p_j_final = df_p_j_final[df_p_j_final['nome_adversario'] == f_adv_j]
        if f_loc_j != "Todos": df_p_j_final = df_p_j_final[df_p_j_final['local'] == f_loc_j]
        if f_fase_j != "Todos": df_p_j_final = df_p_j_final[df_p_j_final['fase'] == f_fase_j]
            
        p_jogadas = len(df_p_j_final)
        p_vitorias = int(df_p_j_final['V'].sum()) if p_jogadas > 0 else 0
        p_empates = int(df_p_j_final['E'].sum()) if p_jogadas > 0 else 0
        p_derrotas = int(df_p_j_final['D'].sum()) if p_jogadas > 0 else 0
        p_aprov_ind = round(((p_vitorias * 3 + p_empates) / (p_jogadas * 3) * 100), 1) if p_jogadas > 0 else 0.0
        
        match_ids_j_final = df_p_j_final['id_partida'].tolist()
        df_ev_j_filtrado = df_ev_j[(df_ev_j['id_jogador'] == id_jog_perfil) & (df_ev_j['id_partida'].isin(match_ids_j_final))]
        
        j_gols = int(df_ev_j_filtrado[df_ev_j_filtrado['tipo_evento'] == 'GOL']['quantidade'].sum())
        j_amarelos = int(df_ev_j_filtrado[df_ev_j_filtrado['tipo_evento'] == 'AMARELO']['quantidade'].sum())
        j_vermelhos = int(df_ev_j_filtrado[df_ev_j_filtrado['tipo_evento'] == 'VERMELHO']['quantidade'].sum())
            
        st.markdown(f"### 📊 Caderno de Desempenho: **{jog_perfil_sel}**")
        jd_col1, jd_col2, jd_col3, jd_col4 = st.columns(4)
        jd_col1.metric("Partidas Jogadas", p_jogadas)
        jd_col2.metric("Vitórias", p_vitorias)
        jd_col3.metric("Empates", p_empates)
        jd_col4.metric("Derrotas", p_derrotas)
        
        jd_col5, jd_col6, jd_col7, jd_col8 = st.columns(4)
        jd_col5.metric("Aproveitamento (%)", f"{p_aprov_ind}%")
        jd_col6.metric("Gols Marcados", j_gols)
        jd_col7.metric("Cartões Amarelos", j_amarelos)
        jd_col8.metric("Cartões Vermelhos", j_vermelhos)