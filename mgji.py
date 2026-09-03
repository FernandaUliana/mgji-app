import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from datetime import datetime
import urllib.parse

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Jurídica - MGJI", layout="wide")

# --- BANCO DE DADOS (Supabase / PostgreSQL) ---
@st.cache_resource
def init_db():
    # O Streamlit vai buscar a URL do banco lá nas configurações secretas da nuvem
    conn = psycopg2.connect(st.secrets["DB_URL"])
    return conn

conn = init_db()

def carregar_dados(tabela):
    return pd.read_sql_query(f"SELECT * FROM {tabela}", conn)

# --- SISTEMA DE AUTENTICAÇÃO (LOGIN) ---
USUARIOS = {
    "admin": "1234",
    "advogado1": "senha123",
    "fernanda": "mgji2026",
    "secretaria": "mgji123"
}

if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario_logado"] = ""

def tela_login():
    st.title("🔒 Acesso ao Sistema MGJI")
    with st.form("form_login"):
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        btn_login = st.form_submit_button("Entrar")
        if btn_login:
            if usuario in USUARIOS and USUARIOS[usuario] == senha:
                st.session_state["autenticado"] = True
                st.session_state["usuario_logado"] = usuario
                st.success(f"Bem-vindo(a), {usuario}!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

if not st.session_state["autenticado"]:
    tela_login()
    st.stop()

# --- BARRA LATERAL (LOGOUT E NAVEGAÇÃO) ---
st.sidebar.write(f"👤 Usuário conectado: **{st.session_state['usuario_logado']}**")
if st.sidebar.button("Sair (Logout)"):
    st.session_state["autenticado"] = False
    st.session_state["usuario_logado"] = ""
    st.rerun()

st.sidebar.title("⚖️ Sistema MGJI")
menu = st.sidebar.radio("Navegação", [
    "📊 Dashboard de BI", 
    "📁 Clientes e Processos", 
    "⏳ Prazos e Workflow",
    "💰 Gestão de Honorários",
    "🚨 Alerta de Prazos (Semáforo)",
    "💬 WhatsApp Automático",
    "📄 Gerador de Documentos"
])

# ==========================================
# TELA 1: DASHBOARD
# ==========================================
if menu == "📊 Dashboard de BI":
    st.title("Painel de Inteligência e KPIs")
    df_prazos = carregar_dados('prazos')
    df_processos = carregar_dados('processos')
    
    if not df_prazos.empty and not df_processos.empty:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Processos Ativos", len(df_processos[df_processos['status'] == 'Ativo']))
        col2.metric("Prazos Pendentes", len(df_prazos[df_prazos['workflow'] != 'Protocolado']))
        col3.metric("Peças em Revisão", len(df_prazos[df_prazos['workflow'] == 'Revisão']))
        
        taxa_conclusao = round((len(df_prazos[df_prazos['workflow'] == 'Protocolado']) / len(df_prazos)) * 100, 1) if len(df_prazos) > 0 else 0
        col4.metric("Taxa de Conclusão (%)", f"{taxa_conclusao}%")
        
        st.markdown("---")
        col_graf1, col_graf2 = st.columns(2)
        
        with col_graf1:
            st.subheader("Carga de Trabalho por Advogado")
            grafico_adv = df_prazos[df_prazos['workflow'] != 'Protocolado']['responsavel'].value_counts().reset_index()
            grafico_adv.columns = ['Advogado', 'Prazos Pendentes']
            fig1 = px.bar(grafico_adv, x='Advogado', y='Prazos Pendentes', color='Advogado', template='plotly_white')
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_graf2:
            st.subheader("Gargalos no Workflow")
            grafico_wf = df_prazos['workflow'].value_counts().reset_index()
            grafico_wf.columns = ['Etapa', 'Quantidade']
            fig2 = px.pie(grafico_wf, values='Quantidade', names='Etapa', hole=0.4, template='plotly_white')
            st.plotly_chart(fig2, use_container_width=True)

# ==========================================
# TELA 2: PROCESSOS
# ==========================================
elif menu == "📁 Clientes e Processos":
    st.title("Gestão de Clientes e Processos")
    
    with st.expander("➕ Novo Processo / Cliente", expanded=True):
        with st.form("form_processo", clear_on_submit=True):
            col1, col2 = st.columns(2)
            cliente = col1.text_input("Nome do Cliente")
            numero = col2.text_input("Número do Processo (CNJ)")
            area = col1.selectbox("Área do Direito", ["Cível", "Trabalhista", "Tributário", "Família", "Penal"])
            status = col2.selectbox("Status", ["Ativo", "Encerrado", "Suspenso"])
            
            if st.form_submit_button("Salvar Processo"):
                usuario_atual = st.session_state["usuario_logado"]
                c = conn.cursor()
                # Nuvem usa %s em vez de ?
                c.execute("INSERT INTO processos (cliente, numero, area, status, criado_por) VALUES (%s, %s, %s, %s, %s)", (cliente, numero, area, status, usuario_atual))
                conn.commit()
                st.success(f"Processo salvo por '{usuario_atual}' com sucesso!")
    
    st.markdown("---")
    aba_geral, aba_usuario = st.tabs(["📋 Base Completa", "👤 Filtrar por Usuário (Auditoria)"])
    df_processos = carregar_dados('processos')
    
    with aba_geral:
        st.subheader("Todos os Processos Cadastrados")
        st.dataframe(df_processos, use_container_width=True, hide_index=True)
        
    with aba_usuario:
        st.subheader("Auditoria de Cadastros por Funcionário")
        if not df_processos.empty and 'criado_por' in df_processos.columns:
            lista_usuarios = ["Todos"] + [u for u in df_processos['criado_por'].dropna().unique()]
            usuario_sel = st.selectbox("Selecione o Usuário:", lista_usuarios)
            df_filtrado = df_processos[df_processos['criado_por'] == usuario_sel] if usuario_sel != "Todos" else df_processos
            st.metric("Total Cadastrado", len(df_filtrado))
            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

# ==========================================
# TELA 3: WORKFLOW
# ==========================================
elif menu == "⏳ Prazos e Workflow":
    st.title("Workflow de Produção e Audiências")
    df_processos = carregar_dados('processos')
    lista_processos = df_processos['numero'].tolist() if not df_processos.empty else ["Nenhum processo cadastrado"]
    
    with st.expander("➕ Inserir Novo Prazo / Audiência"):
        with st.form("form_prazo", clear_on_submit=True):
            col1, col2 = st.columns(2)
            processo = col1.selectbox("Processo Relacionado", lista_processos)
            tipo = col2.text_input("Descrição (Ex: Apelação, Audiência)")
            data_fatal = col1.date_input("Data Fatal (D-0)")
            responsavel = col2.text_input("Advogado Responsável")
            workflow = st.selectbox("Status Atual (Workflow)", ["Triagem (A Fazer)", "Em Elaboração", "Revisão", "Protocolado"])
            
            if st.form_submit_button("Salvar Prazo"):
                usuario_atual = st.session_state["usuario_logado"]
                c = conn.cursor()
                c.execute("INSERT INTO prazos (processo, tipo, data_fatal, responsavel, workflow, criado_por) VALUES (%s, %s, %s, %s, %s, %s)",(processo, tipo, data_fatal, responsavel, workflow, usuario_atual))
                conn.commit()
                st.success(f"Prazo agendado por '{usuario_atual}' com sucesso!")

    st.subheader("Auditoria Operacional (Prazos Pendentes)")
    df_prazos = carregar_dados('prazos')
    if not df_prazos.empty:
        filtro_responsavel = st.selectbox("Filtrar por Responsável", ["Todos"] + df_prazos['responsavel'].unique().tolist())
        if filtro_responsavel != "Todos":
            df_prazos = df_prazos[df_prazos['responsavel'] == filtro_responsavel]
            
        aba1, aba2, aba3, aba4 = st.tabs(["🔴 A Fazer", "🟡 Em Elaboração", "🟠 Em Revisão", "🟢 Concluídos"])
        with aba1: st.dataframe(df_prazos[df_prazos['workflow'] == 'Triagem (A Fazer)'], hide_index=True, use_container_width=True)
        with aba2: st.dataframe(df_prazos[df_prazos['workflow'] == 'Em Elaboração'], hide_index=True, use_container_width=True)
        with aba3: st.dataframe(df_prazos[df_prazos['workflow'] == 'Revisão'], hide_index=True, use_container_width=True)
        with aba4: st.dataframe(df_prazos[df_prazos['workflow'] == 'Protocolado'], hide_index=True, use_container_width=True)

# ==========================================
# TELA 4: HONORÁRIOS
# ==========================================
elif menu == "💰 Gestão de Honorários":
    st.title("💰 Gestão e Mensuração de Honorários")
    st.write("Controle os recebimentos e a projeção de faturamento do escritório.")

    df_processos = carregar_dados('processos')
    lista_processos = df_processos['numero'].tolist() if not df_processos.empty else ["Nenhum processo"]

    with st.expander("➕ Lançar Novos Honorários", expanded=True):
        with st.form("form_honorarios", clear_on_submit=True):
            col1, col2 = st.columns(2)
            processo_hon = col1.selectbox("Vincular ao Processo (CNJ)", lista_processos)
            valor_hon = col2.number_input("Valor do Honorário (R$)", min_value=0.0, format="%.2f")
            tipo_hon = col1.selectbox("Tipo de Cobrança", ["Contratual (Pró-labore)", "Êxito", "Partido", "Consulta/Diligência"])
            status_hon = col2.radio("Status do Pagamento", ["Pendente", "Pago"], horizontal=True)

            if st.form_submit_button("Registrar Honorários"):
                c = conn.cursor()
                c.execute("INSERT INTO honorarios (processo, valor, tipo, status) VALUES (%s, %s, %s, %s)", (processo_hon, valor_hon, tipo_hon, status_hon))
                conn.commit()
                st.success("Valor registrado com sucesso no fluxo de caixa!")

    st.markdown("---")
    st.subheader("Resumo Financeiro (Faturamento)")
    
    df_honorarios = carregar_dados('honorarios')
    if not df_honorarios.empty:
        total_pago = df_honorarios[df_honorarios['status'] == 'Pago']['valor'].sum()
        total_pendente = df_honorarios[df_honorarios['status'] == 'Pendente']['valor'].sum()

        colA, colB, colC = st.columns(3)
        colA.metric("🟢 Total Recebido (Em Caixa)", f"R$ {total_pago:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        colB.metric("🔴 Total a Receber (Pendente)", f"R$ {total_pendente:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        colC.metric("📊 Volume Total Negociado", f"R$ {(total_pago + total_pendente):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        st.dataframe(df_honorarios, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum honorário registrado ainda. Faça o primeiro lançamento acima.")

# ==========================================
# TELA 5: SEMÁFORO DE PRAZOS
# ==========================================
elif menu == "🚨 Alerta de Prazos (Semáforo)":
    st.title("🚨 Controle Visual de Prazos")
    st.write("Visão unificada para evitar perda de prazos fatais.")
    
    df_prazos = carregar_dados('prazos')

    if not df_prazos.empty:
        df_prazos['data_fatal'] = pd.to_datetime(df_prazos['data_fatal']).dt.date
        hoje = datetime.now().date()

        def gerar_semaforo(data_prazo):
            if pd.isnull(data_prazo): return "⚪ SEM DATA"
            dias = (data_prazo - hoje).days
            if dias < 0: return "⚫ VENCIDO"
            elif dias <= 3: return "🔴 URGENTE"
            elif dias <= 7: return "🟡 ATENÇÃO"
            else: return "🟢 TRANQUILO"

        df_prazos['Alerta de Prazo'] = df_prazos['data_fatal'].apply(gerar_semaforo)

        df_visual = df_prazos[['processo', 'Alerta de Prazo', 'data_fatal', 'tipo', 'responsavel', 'workflow']]
        st.dataframe(df_visual, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum prazo cadastrado no banco de dados ainda.")

# ==========================================
# TELA 6: WHATSAPP AUTOMÁTICO
# ==========================================
elif menu == "💬 WhatsApp Automático":
    st.title("💬 Atualização de Clientes (WhatsApp)")
    st.write("Notifique seus clientes sobre o andamento do processo com um clique.")
    
    df_processos = carregar_dados('processos')

    if not df_processos.empty:
        cliente_selecionado = st.selectbox("Selecione o Cliente:", df_processos['cliente'].unique())
        
        dados_cliente = df_processos[df_processos['cliente'] == cliente_selecionado].iloc[0]
        telefone = st.text_input("Telefone do Cliente (DDD + Número. Ex: 5511999999999):", value="5511999999999")

        mensagem = f"Olá, {dados_cliente['cliente']}, tudo bem? O seu processo (Nº {dados_cliente['numero']} - Ação {dados_cliente['area']}) teve movimentação. O status atual no sistema é: *{dados_cliente['status']}*. Qualquer dúvida, o escritório está à disposição!"

        st.info(f"**Pré-visualização da Mensagem:**\n\n{mensagem}")

        if telefone:
            msg_codificada = urllib.parse.quote(mensagem)
            link_whatsapp = f"https://wa.me/{telefone}?text={msg_codificada}"
            st.link_button(f"Abrir WhatsApp de {dados_cliente['cliente']}", link_whatsapp)
    else:
        st.warning("Cadastre clientes na aba 'Clientes e Processos' primeiro para usar o WhatsApp.")

# ==========================================
# TELA 7: GERADOR DE DOCUMENTOS
# ==========================================
elif menu == "📄 Gerador de Documentos":
    st.title("📄 Gerador Rápido de Procuração")
    st.write("Gere documentos pré-preenchidos com os dados do banco.")
    
    df_processos = carregar_dados('processos')

    if not df_processos.empty:
        cliente_selecionado = st.selectbox("Selecione o Cliente:", df_processos['cliente'].unique())
        dados_cliente = df_processos[df_processos['cliente'] == cliente_selecionado].iloc[0]

        col1, col2 = st.columns(2)
        cpf = col1.text_input("Digite o CPF do cliente:")
        rg = col2.text_input("Digite o RG do cliente:")

        if st.button("Gerar Documento"):
            if cpf and rg:
                texto_procuracao = f"""PROCURAÇÃO AD JUDICIA ET EXTRA

OUTORGANTE: {cliente_selecionado}, portador(a) do RG nº {rg} e CPF nº {cpf}.
OUTORGADO: MGJI Advogados Associados, escritório de advocacia...

Pelo presente instrumento, o outorgante nomeia e constitui seus bastantes procuradores para representá-lo na ação de natureza {dados_cliente['area']} referente ao processo nº {dados_cliente['numero']}.

Belém, {datetime.now().strftime("%d de %B de %Y")}.

___________________________________________________
Assinatura: {cliente_selecionado}
"""
                st.success("Documento gerado com sucesso!")
                st.text_area("Pré-visualização:", texto_procuracao, height=300)

                st.download_button(
                    label="Baixar Procuração (.txt)",
                    data=texto_procuracao,
                    file_name=f"Procuracao_{cliente_selecionado.replace(' ', '_')}.txt",
                    mime="text/plain"
                )
            else:
                st.warning("Preencha o CPF e o RG para gerar o documento.")
    else:
        st.warning("Cadastre clientes primeiro para gerar documentos.")