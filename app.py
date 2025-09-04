import os
import logging
import uuid
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import datetime, date, time
import json

# Configure logging com formato melhorado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console
        logging.FileHandler('sistema_agendamento.log', mode='a')  # Arquivo
    ]
)

# Logger específico para o sistema
logger = logging.getLogger('SistemaAgendamento')

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-joao-layon-2025")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the PostgreSQL database
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL environment variable is not set")

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the app with the extension
db.init_app(app)

with app.app_context():
    # Import models to ensure tables are created
    from models import Paciente, Especialidade, Medico, HorarioDisponivel, Agendamento, Conversa, Local, Configuracao, AgendamentoRecorrente
    db.create_all()
    
    # Import services after models are loaded
    from ai_service import chatbot_service
    
    # Criar locais iniciais se não existirem
    if Local.query.count() == 0:
        locais = [
            Local(nome="Contagem", endereco="Rua Principal, 123", cidade="Contagem", telefone="(31) 3333-4444"),
            Local(nome="Belo Horizonte", endereco="Av. Central, 456", cidade="Belo Horizonte", telefone="(31) 2222-5555")
        ]
        
        for local in locais:
            db.session.add(local)
        
        db.session.commit()
    
    # Criar dados iniciais se não existirem
    if Especialidade.query.count() == 0:
        especialidades = [
            Especialidade(nome="Clínica Geral", descricao="Consultas gerais e check-ups"),
            Especialidade(nome="Cardiologia", descricao="Especialista em coração"),
            Especialidade(nome="Dermatologia", descricao="Cuidados com a pele"),
            Especialidade(nome="Pediatria", descricao="Especialista em crianças"),
            Especialidade(nome="Ginecologia", descricao="Saúde da mulher"),
            Especialidade(nome="Ortopedia", descricao="Ossos e articulações"),
            Especialidade(nome="Psiquiatria", descricao="Saúde mental"),
            Especialidade(nome="Oftalmologia", descricao="Cuidados com os olhos")
        ]
        
        for esp in especialidades:
            db.session.add(esp)
        
        db.session.commit()
        
        # Criar médicos de exemplo
        medicos = [
            Medico(nome="Dr. João Silva", crm="12345-SP", especialidade_id=1),
            Medico(nome="Dra. Maria Santos", crm="23456-SP", especialidade_id=2),
            Medico(nome="Dr. Carlos Oliveira", crm="34567-SP", especialidade_id=3),
            Medico(nome="Dra. Ana Costa", crm="45678-SP", especialidade_id=4),
            Medico(nome="Dr. Pedro Lima", crm="56789-SP", especialidade_id=5),
            Medico(nome="Dra. Julia Fernandes", crm="67890-SP", especialidade_id=6)
        ]
        
        for medico in medicos:
            db.session.add(medico)
        
        db.session.commit()
        
        # Buscar locais criados
        local_contagem = Local.query.filter_by(nome="Contagem").first()
        local_bh = Local.query.filter_by(nome="Belo Horizonte").first()
        
        # Criar horários de exemplo com locais específicos
        # Dr. João Silva (Clínica Geral) - Contagem segunda a sexta
        medico_joao = Medico.query.filter_by(nome="Dr. João Silva").first()
        if medico_joao:
            for dia_semana in range(5):  # Segunda a sexta
                horario = HorarioDisponivel(
                    medico_id=medico_joao.id,
                    local_id=local_contagem.id,
                    dia_semana=dia_semana,
                    hora_inicio=time(8, 0),
                    hora_fim=time(17, 0),
                    duracao_consulta=30
                )
                db.session.add(horario)
        
        # Dra. Maria Santos (Cardiologia) - BH quarta e quinta, Contagem segunda e terça
        medico_maria = Medico.query.filter_by(nome="Dra. Maria Santos").first()
        if medico_maria:
            # Segunda e terça em Contagem
            for dia_semana in [0, 1]:  # Segunda, terça
                horario = HorarioDisponivel(
                    medico_id=medico_maria.id,
                    local_id=local_contagem.id,
                    dia_semana=dia_semana,
                    hora_inicio=time(8, 0),
                    hora_fim=time(12, 0),
                    duracao_consulta=30
                )
                db.session.add(horario)
            
            # Quarta e quinta em BH
            for dia_semana in [2, 3]:  # Quarta, quinta
                horario = HorarioDisponivel(
                    medico_id=medico_maria.id,
                    local_id=local_bh.id,
                    dia_semana=dia_semana,
                    hora_inicio=time(13, 0),
                    hora_fim=time(17, 0),
                    duracao_consulta=30
                )
                db.session.add(horario)
        
        # Outros médicos com horários padrão em Contagem
        outros_medicos = [medico for medico in medicos if medico.nome not in ["Dr. João Silva", "Dra. Maria Santos"]]
        for medico in outros_medicos:
            for dia_semana in range(5):  # Segunda a sexta
                horario = HorarioDisponivel(
                    medico_id=medico.id,
                    local_id=local_contagem.id,
                    dia_semana=dia_semana,
                    hora_inicio=time(8, 0),
                    hora_fim=time(18, 0),
                    duracao_consulta=30
                )
                db.session.add(horario)
        
        db.session.commit()
    
    # Criar configurações iniciais se não existirem
    if Configuracao.query.count() == 0:
        configuracoes_iniciais = [
            ('nome_clinica', 'Clínica João Layon', 'Nome da clínica exibido no sistema'),
            ('nome_assistente', 'Assistente Virtual', 'Nome do assistente de agendamentos'),
            ('telefone_clinica', '(31) 3333-4444', 'Telefone principal da clínica'),
            ('email_admin', 'joao@gmail.com', 'Email do administrador'),
            ('senha_admin', '30031936Vo', 'Senha do administrador'),
            ('horario_funcionamento', 'Segunda a Sexta, 8h às 18h', 'Horário de funcionamento da clínica'),
            ('bloquear_especialidades_duplicadas', 'false', 'Impedir paciente ter agendamentos em especialidades iguais'),
            ('duracao_agendamento_recorrente', '4', 'Duração em semanas para agendamentos recorrentes')
        ]
        
        for chave, valor, descricao in configuracoes_iniciais:
            Configuracao.set_valor(chave, valor, descricao)

@app.route('/')
def index():
    """Página principal do chatbot"""
    return render_template('chat.html')

@app.route('/agendamentos')
def listar_agendamentos():
    """Lista todos os agendamentos (apenas administradores)"""
    # Esta página é apenas para administradores
    # Em uma implementação real, você adicionaria autenticação aqui
    agendamentos = Agendamento.query.order_by(Agendamento.data, Agendamento.hora).all()
    return render_template('agendamentos.html', agendamentos=agendamentos, admin=True)

@app.route('/chat', methods=['POST'])
def processar_chat():
    """Processa mensagem do chatbot"""
    try:
        dados = request.get_json()
        mensagem = dados.get('mensagem', '').strip()
        
        if not mensagem:
            return jsonify({
                'success': False,
                'message': 'Mensagem vazia.'
            })
        
        # Obter ou criar sessão de conversa
        session_id = session.get('chat_session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            session['chat_session_id'] = session_id
        
        # Buscar conversa existente
        conversa = Conversa.query.filter_by(session_id=session_id).first()
        if not conversa:
            conversa = Conversa(session_id=session_id, estado='inicio')
            db.session.add(conversa)
            db.session.commit()
        
        # Atualizar timestamp da conversa
        conversa.atualizado_em = datetime.utcnow()
        
        # Limpeza proativa de sessões abandonadas (5% das vezes)
        import random
        if random.randint(1, 20) == 1:
            try:
                from datetime import timedelta
                data_limite = datetime.utcnow() - timedelta(hours=6)
                conversas_abandonadas = Conversa.query.filter(
                    Conversa.atualizado_em < data_limite,
                    Conversa.estado.notin_(['finalizado'])
                ).limit(5).all()
                
                if conversas_abandonadas:
                    for conv in conversas_abandonadas:
                        db.session.delete(conv)
                    logger.info(f"Limpeza: {len(conversas_abandonadas)} conversas abandonadas removidas")
            except Exception as cleanup_error:
                logger.warning(f"Erro na limpeza: {cleanup_error}")
        
        # Processar mensagem com IA
        resposta = chatbot_service.processar_mensagem(mensagem, conversa)
        
        # MELHORIA: Adicionar timestamp para cache busting em horários
        if resposta.get('tipo') in ['horarios', 'horarios_atualizados']:
            resposta['timestamp'] = datetime.utcnow().isoformat()
            resposta['cache_key'] = f"horarios_{datetime.utcnow().timestamp()}"
        
        # Salvar mudanças na conversa
        db.session.commit()
        
        return jsonify(resposta)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Erro crítico no processamento do chat - Sessão: {session.get('chat_session_id', 'N/A')} - Mensagem: '{mensagem}' - Erro: {e}\n{error_details}")
        return jsonify({
            'success': False,
            'message': 'Erro interno do servidor. Nossa equipe foi notificada. Tente novamente em alguns minutos.',
            'error_id': f"ERR_{int(datetime.utcnow().timestamp())}"
        })

@app.route('/especialidades')
def listar_especialidades():
    """API para listar especialidades ativas"""
    especialidades = Especialidade.query.filter_by(ativo=True).all()
    return jsonify([esp.to_dict() for esp in especialidades])

@app.route('/locais')
def listar_locais():
    """API para listar locais ativos"""
    locais = Local.query.filter_by(ativo=True).all()
    return jsonify([local.to_dict() for local in locais])

@app.route('/api/verificar-disponibilidade', methods=['POST'])
def verificar_disponibilidade():
    """API para verificar se um horário específico ainda está disponível"""
    try:
        dados = request.get_json()
        medico_id = dados.get('medico_id')
        data_str = dados.get('data')  # formato: YYYY-MM-DD
        hora_str = dados.get('hora')  # formato: HH:MM
        
        if not all([medico_id, data_str, hora_str]):
            return jsonify({'disponivel': False, 'motivo': 'Dados incompletos'})
        
        # Converter para objetos datetime
        from datetime import datetime
        data_agendamento = datetime.strptime(data_str, '%Y-%m-%d').date()
        hora_agendamento = datetime.strptime(hora_str, '%H:%M').time()
        
        # Verificar agendamento normal
        agendamento_existente = Agendamento.query.filter_by(
            medico_id=medico_id,
            data=data_agendamento,
            hora=hora_agendamento,
            status='agendado'
        ).first()
        
        if agendamento_existente:
            return jsonify({
                'disponivel': False, 
                'motivo': 'Horário já ocupado por outro paciente',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Verificar agendamento recorrente
        dia_semana = data_agendamento.weekday()
        agendamento_recorrente = AgendamentoRecorrente.query.filter(
            AgendamentoRecorrente.medico_id == medico_id,
            AgendamentoRecorrente.dia_semana == dia_semana,
            AgendamentoRecorrente.hora == hora_agendamento,
            AgendamentoRecorrente.ativo == True,
            AgendamentoRecorrente.data_inicio <= data_agendamento,
            (AgendamentoRecorrente.data_fim.is_(None)) | (AgendamentoRecorrente.data_fim >= data_agendamento)
        ).first()
        
        if agendamento_recorrente:
            return jsonify({
                'disponivel': False, 
                'motivo': 'Horário bloqueado por agendamento recorrente',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        return jsonify({
            'disponivel': True, 
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Erro ao verificar disponibilidade: {e}")
        return jsonify({'disponivel': False, 'motivo': 'Erro interno'})

@app.route('/cancelar/<int:agendamento_id>', methods=['POST'])
def cancelar_agendamento(agendamento_id):
    """Cancela um agendamento (admin)"""
    try:
        agendamento = Agendamento.query.get_or_404(agendamento_id)
        agendamento.status = 'cancelado'
        agendamento.cancelado_em = datetime.utcnow()
        agendamento.motivo_cancelamento = 'Cancelado pela administração'
        db.session.commit()
        
        flash('Agendamento cancelado com sucesso!', 'success')
        return redirect(url_for('listar_agendamentos'))
        
    except Exception as e:
        logging.error(f"Erro ao cancelar agendamento: {e}")
        flash('Erro ao cancelar agendamento. Tente novamente.', 'error')
        return redirect(url_for('listar_agendamentos'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Página de login do administrador"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '').strip()
        
        email_admin = Configuracao.get_valor('email_admin', 'joao@gmail.com')
        senha_admin = Configuracao.get_valor('senha_admin', '30031936Vo')
        
        if email == email_admin and senha == senha_admin:
            session['admin_logado'] = True
            session['admin_email'] = email
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Email ou senha incorretos.', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Logout do administrador"""
    session.pop('admin_logado', None)
    session.pop('admin_email', None)
    flash('Logout realizado com sucesso!', 'info')
    return redirect(url_for('admin_login'))

def requer_login_admin(f):
    """Decorator para proteger rotas administrativas"""
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logado'):
            flash('Acesso negado. Faça login como administrador.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/admin')
@requer_login_admin
def admin():
    """Página administrativa"""
    especialidades = Especialidade.query.all()
    medicos = Medico.query.all()
    locais = Local.query.all()
    horarios_disponiveis = HorarioDisponivel.query.all()
    pacientes = Paciente.query.order_by(Paciente.nome).all()
    
    # Agrupar horários por médico para melhor visualização
    horarios_agrupados = {}
    for horario in horarios_disponiveis:
        medico_nome = horario.medico_rel.nome if horario.medico_rel else 'Médico não encontrado'
        medico_id = horario.medico_id
        chave = f"{medico_id}_{medico_nome}"
        if chave not in horarios_agrupados:
            horarios_agrupados[chave] = {
                'medico_nome': medico_nome,
                'medico_id': medico_id,
                'horarios': []
            }
        horarios_agrupados[chave]['horarios'].append(horario)
    
    # Estatísticas
    total_pacientes = Paciente.query.count()
    total_agendamentos = Agendamento.query.count()
    agendamentos_hoje = Agendamento.query.filter_by(
        data=date.today(),
        status='agendado'
    ).count()
    total_especialidades = Especialidade.query.filter_by(ativo=True).count()
    
    # Stats por especialidade para relatórios
    agendamentos_por_especialidade = []
    for esp in especialidades:
        total = Agendamento.query.filter_by(especialidade_id=esp.id).count()
        agendados = Agendamento.query.filter_by(especialidade_id=esp.id, status='agendado').count()
        concluidos = Agendamento.query.filter_by(especialidade_id=esp.id, status='concluido').count()
        cancelados = Agendamento.query.filter_by(especialidade_id=esp.id, status='cancelado').count()
        
        if total > 0:  # Só incluir especialidades com agendamentos
            agendamentos_por_especialidade.append({
                'especialidade': esp.nome,
                'total': total,
                'agendados': agendados,
                'concluidos': concluidos,
                'cancelados': cancelados
            })
    
    # Relatório de pacientes por especialidade 
    pacientes_especialidades = []
    for paciente in pacientes:
        # Buscar todas as especialidades que este paciente já consultou/agendou
        especialidades_paciente = db.session.query(Especialidade.nome).join(
            Agendamento, Agendamento.especialidade_id == Especialidade.id
        ).filter(Agendamento.paciente_id == paciente.id).distinct().all()
        
        if especialidades_paciente:  # Só incluir pacientes que têm agendamentos
            especialidades_nomes = [esp[0] for esp in especialidades_paciente]
            pacientes_especialidades.append({
                'nome': paciente.nome,
                'cpf': paciente.cpf,
                'especialidades': especialidades_nomes,
                'total_agendamentos': len(paciente.agendamentos)
            })
    
    return render_template('admin.html',
                         especialidades=especialidades,
                         medicos=medicos,
                         locais=locais,
                         horarios_disponiveis=horarios_disponiveis,
                         horarios_agrupados=horarios_agrupados,
                         pacientes=pacientes,
                         total_pacientes=total_pacientes,
                         total_agendamentos=total_agendamentos,
                         agendamentos_hoje=agendamentos_hoje,
                         total_especialidades=total_especialidades,
                         agendamentos_por_especialidade=agendamentos_por_especialidade,
                         pacientes_especialidades=pacientes_especialidades)

@app.route('/admin/config')
@requer_login_admin
def admin_config():
    """Página de configurações"""
    configuracoes = {}
    chaves_config = ['nome_clinica', 'nome_assistente', 'telefone_clinica', 'email_admin', 'horario_funcionamento', 'bloquear_especialidades_duplicadas', 'duracao_agendamento_recorrente']
    
    for chave in chaves_config:
        configuracoes[chave] = Configuracao.get_valor(chave, '')
    
    return render_template('admin_config.html', configuracoes=configuracoes, locais=Local.query.all())

@app.route('/admin/config', methods=['POST'])
@requer_login_admin
def salvar_config():
    """Salvar configurações"""
    try:
        nome_clinica = request.form.get('nome_clinica', '').strip()
        nome_assistente = request.form.get('nome_assistente', '').strip()
        telefone_clinica = request.form.get('telefone_clinica', '').strip()
        email_admin = request.form.get('email_admin', '').strip()
        senha_admin = request.form.get('senha_admin', '').strip()
        horario_funcionamento = request.form.get('horario_funcionamento', '').strip()
        bloquear_especialidades = request.form.get('bloquear_especialidades_duplicadas')
        duracao_recorrente = request.form.get('duracao_agendamento_recorrente', '').strip()
        
        if nome_clinica:
            Configuracao.set_valor('nome_clinica', nome_clinica)
        if nome_assistente:
            Configuracao.set_valor('nome_assistente', nome_assistente)
        if telefone_clinica:
            Configuracao.set_valor('telefone_clinica', telefone_clinica)
        if email_admin:
            Configuracao.set_valor('email_admin', email_admin)
        if senha_admin:
            Configuracao.set_valor('senha_admin', senha_admin)
        if horario_funcionamento:
            Configuracao.set_valor('horario_funcionamento', horario_funcionamento)
        
        # Configurações de checkbox
        Configuracao.set_valor('bloquear_especialidades_duplicadas', 'true' if bloquear_especialidades else 'false')
        
        if duracao_recorrente and duracao_recorrente.isdigit():
            Configuracao.set_valor('duracao_agendamento_recorrente', duracao_recorrente)
        
        flash('Configurações salvas com sucesso!', 'success')
        return redirect(url_for('admin_config'))
        
    except Exception as e:
        logging.error(f"Erro ao salvar configurações: {e}")
        flash('Erro ao salvar configurações. Tente novamente.', 'error')
        return redirect(url_for('admin_config'))

@app.route('/admin/especialidades', methods=['POST'])
@requer_login_admin
def admin_especialidades():
    """Cadastrar nova especialidade"""
    try:
        nome = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip()
        
        if not nome:
            flash('Nome da especialidade é obrigatório.', 'error')
            return redirect(url_for('admin'))
        
        # Verificar se já existe
        existe = Especialidade.query.filter_by(nome=nome).first()
        if existe:
            flash('Especialidade já existe.', 'error')
            return redirect(url_for('admin'))
        
        nova_especialidade = Especialidade(
            nome=nome,
            descricao=descricao if descricao else None
        )
        
        db.session.add(nova_especialidade)
        db.session.commit()
        
        flash(f'Especialidade "{nome}" cadastrada com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        logging.error(f"Erro ao cadastrar especialidade: {e}")
        flash('Erro ao cadastrar especialidade. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/medicos', methods=['POST'])
@requer_login_admin
def admin_medicos():
    """Cadastrar novo médico"""
    try:
        nome = request.form.get('nome', '').strip()
        crm = request.form.get('crm', '').strip()
        especialidade_id_str = request.form.get('especialidade_id')
        
        # Validação de campos obrigatórios
        if not nome or not crm or not especialidade_id_str:
            flash('Todos os campos obrigatórios devem ser preenchidos.', 'error')
            return redirect(url_for('admin'))
            
        # Validação e conversão segura
        try:
            especialidade_id = int(especialidade_id_str)
            if especialidade_id <= 0:
                raise ValueError("ID de especialidade deve ser positivo")
        except (ValueError, TypeError):
            flash('Especialidade inválida selecionada.', 'error')
            return redirect(url_for('admin'))
        
        # Validação de formato do CRM
        if len(crm) < 4 or not any(c.isdigit() for c in crm):
            flash('CRM deve conter pelo menos 4 caracteres e números.', 'error')
            return redirect(url_for('admin'))
        
        # Verificar se CRM já existe
        existe = Medico.query.filter_by(crm=crm).first()
        if existe:
            flash('CRM já cadastrado.', 'error')
            return redirect(url_for('admin'))
        
        try:
            novo_medico = Medico(
                nome=nome,
                crm=crm,
                especialidade_id=especialidade_id
            )
            
            db.session.add(novo_medico)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logging.error(f"Erro ao salvar médico: {e}")
            if 'UNIQUE constraint failed' in str(e):
                flash('CRM já cadastrado no sistema.', 'error')
            else:
                flash('Erro ao cadastrar médico. Tente novamente.', 'error')
            return redirect(url_for('admin'))
        
        # Criar horários padrão (Segunda a Sexta, 8h às 18h) no primeiro local disponível
        primeiro_local = Local.query.first()
        if primeiro_local:
            for dia_semana in range(5):  # Segunda a sexta
                horario = HorarioDisponivel(
                    medico_id=novo_medico.id,
                    local_id=primeiro_local.id,
                    dia_semana=dia_semana,
                    hora_inicio=time(8, 0),
                    hora_fim=time(18, 0),
                    duracao_consulta=30
                )
                db.session.add(horario)
        
        db.session.commit()
        
        flash(f'Médico "{nome}" cadastrado com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro crítico ao cadastrar médico: {e}")
        flash('Erro interno no sistema. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/medicos/<int:medico_id>/toggle-recorrencia', methods=['POST'])
@requer_login_admin
def toggle_medico_recorrencia(medico_id):
    """Ativar/desativar agenda recorrente do médico"""
    try:
        medico = Medico.query.get_or_404(medico_id)
        medico.agenda_recorrente = not medico.agenda_recorrente
        db.session.commit()
        
        status = "ativada" if medico.agenda_recorrente else "desativada"
        flash(f'Agenda recorrente {status} para {medico.nome}!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao alterar configuração do médico: {e}")
        flash('Erro ao alterar configuração. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/medicos/<int:medico_id>/edit', methods=['GET', 'POST'])
@requer_login_admin
def editar_medico(medico_id):
    """Editar médico"""
    try:
        medico = Medico.query.get_or_404(medico_id)
        
        if request.method == 'POST':
            nome = request.form.get('nome', '').strip()
            crm = request.form.get('crm', '').strip()
            especialidade_id_str = request.form.get('especialidade_id')
            agenda_recorrente = request.form.get('agenda_recorrente') == 'on'
            
            # Validação de campos obrigatórios
            if not nome or not crm or not especialidade_id_str:
                flash('Todos os campos obrigatórios devem ser preenchidos.', 'error')
                return redirect(url_for('editar_medico', medico_id=medico_id))
            
            try:
                especialidade_id = int(especialidade_id_str)
                if especialidade_id <= 0:
                    raise ValueError("ID de especialidade deve ser positivo")
            except (ValueError, TypeError):
                flash('Especialidade inválida selecionada.', 'error')
                return redirect(url_for('editar_medico', medico_id=medico_id))
            
            # Verificar se CRM já existe para outro médico
            existe = Medico.query.filter(Medico.crm == crm, Medico.id != medico_id).first()
            if existe:
                flash('CRM já cadastrado para outro médico.', 'error')
                return redirect(url_for('editar_medico', medico_id=medico_id))
            
            # Atualizar médico
            medico.nome = nome
            medico.crm = crm
            medico.especialidade_id = especialidade_id
            medico.agenda_recorrente = agenda_recorrente
            
            db.session.commit()
            flash(f'Médico "{nome}" atualizado com sucesso!', 'success')
            return redirect(url_for('admin'))
        
        # GET: mostrar formulário de edição
        especialidades = Especialidade.query.filter_by(ativo=True).all()
        return render_template('editar_medico.html', medico=medico, especialidades=especialidades)
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao editar médico: {e}")
        flash('Erro interno ao editar médico. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/horarios', methods=['POST'])
@requer_login_admin
def admin_horarios():
    """Configurar horários de médico"""
    try:
        horario_id = request.form.get('horario_id')  # Para edição
        medico_id_str = request.form.get('medico_id')
        local_id_str = request.form.get('local_id')
        dia_semana_str = request.form.get('dia_semana')
        hora_inicio = request.form.get('hora_inicio')
        hora_fim = request.form.get('hora_fim')
        duracao_consulta_str = request.form.get('duracao_consulta', '30')
        
        # Validação robusta de campos obrigatórios
        if not all([medico_id_str, local_id_str, dia_semana_str, hora_inicio, hora_fim]):
            flash('Todos os campos são obrigatórios.', 'error')
            return redirect(url_for('admin'))
            
        # Validação e conversão segura de tipos
        try:
            medico_id = int(medico_id_str) if medico_id_str else 0
            local_id = int(local_id_str) if local_id_str else 0
            dia_semana = int(dia_semana_str) if dia_semana_str else 0
            duracao_consulta = int(duracao_consulta_str)
            
            if medico_id <= 0 or local_id <= 0 or dia_semana < 0 or dia_semana > 6:
                raise ValueError("IDs devem ser positivos e dia da semana entre 0-6")
                
        except (ValueError, TypeError) as e:
            logging.error(f"Erro de validação em admin_horarios: {e}")
            flash('Dados inválidos fornecidos. Verifique os valores.', 'error')
            return redirect(url_for('admin'))
        
        if horario_id:
            # Editar horário existente - validação segura
            try:
                horario_id_int = int(horario_id)
                if horario_id_int <= 0:
                    raise ValueError("ID do horário inválido")
                horario = HorarioDisponivel.query.get(horario_id_int)
            except (ValueError, TypeError):
                flash('ID de horário inválido.', 'error')
                return redirect(url_for('admin'))
            if horario:
                try:
                    horario.medico_id = medico_id
                    horario.local_id = local_id
                    horario.dia_semana = dia_semana
                    horario.hora_inicio = datetime.strptime(hora_inicio, '%H:%M').time() if hora_inicio else None
                    horario.hora_fim = datetime.strptime(hora_fim, '%H:%M').time() if hora_fim else None
                    horario.duracao_consulta = duracao_consulta
                    db.session.commit()
                    flash('Horário atualizado com sucesso!', 'success')
                except ValueError as e:
                    db.session.rollback()
                    logging.error(f"Erro ao atualizar horário: {e}")
                    flash('Formato de hora inválido. Use HH:MM', 'error')
                    return redirect(url_for('admin'))
            else:
                flash('Horário não encontrado.', 'error')
                return redirect(url_for('admin'))
        else:
            # Verificar se já existe configuração para este médico/local/dia
            existe = HorarioDisponivel.query.filter_by(
                medico_id=medico_id,
                local_id=local_id,
                dia_semana=dia_semana
            ).first()
            
            if existe:
                flash('Já existe horário configurado para este médico neste dia e local.', 'warning')
                return redirect(url_for('admin'))
            
            # Criar novo com validação
            try:
                novo_horario = HorarioDisponivel(
                    medico_id=medico_id,
                    local_id=local_id,
                    dia_semana=dia_semana,
                    hora_inicio=datetime.strptime(hora_inicio, '%H:%M').time() if hora_inicio else None,
                    hora_fim=datetime.strptime(hora_fim, '%H:%M').time() if hora_fim else None,
                    duracao_consulta=duracao_consulta
                )
                db.session.add(novo_horario)
                db.session.commit()
                flash('Horário criado com sucesso!', 'success')
            except ValueError as e:
                db.session.rollback()
                logging.error(f"Erro ao criar horário: {e}")
                flash('Formato de hora inválido. Use HH:MM', 'error')
                return redirect(url_for('admin'))
        return redirect(url_for('admin'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro crítico ao configurar horário: {e}")
        flash('Erro interno ao configurar horário. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/locais', methods=['POST'])
@requer_login_admin
def admin_locais():
    """Cadastrar ou editar local de atendimento"""
    try:
        local_id = request.form.get('local_id', '').strip()
        nome = request.form.get('nome', '').strip()
        endereco = request.form.get('endereco', '').strip()
        cidade = request.form.get('cidade', '').strip()
        telefone = request.form.get('telefone', '').strip()
        
        if not nome or not cidade:
            flash('Nome e cidade são obrigatórios.', 'error')
            return redirect(url_for('admin'))
        
        if local_id:
            # Editar local existente
            try:
                local_id_int = int(local_id)
                local = Local.query.get(local_id_int)
                if local:
                    # Verificar se nome já existe em outro local
                    existe = Local.query.filter(Local.nome == nome, Local.id != local_id_int).first()
                    if existe:
                        flash('Já existe outro local com este nome.', 'error')
                        return redirect(url_for('admin'))
                    
                    local.nome = nome
                    local.endereco = endereco if endereco else None
                    local.cidade = cidade
                    local.telefone = telefone if telefone else None
                    db.session.commit()
                    flash(f'Local "{nome}" atualizado com sucesso!', 'success')
                else:
                    flash('Local não encontrado.', 'error')
            except (ValueError, TypeError):
                flash('ID de local inválido.', 'error')
        else:
            # Verificar se já existe
            existe = Local.query.filter_by(nome=nome).first()
            if existe:
                flash('Local já existe.', 'error')
                return redirect(url_for('admin'))
            
            novo_local = Local(
                nome=nome,
                endereco=endereco if endereco else None,
                cidade=cidade,
                telefone=telefone if telefone else None
            )
            
            db.session.add(novo_local)
            db.session.commit()
            flash(f'Local "{nome}" cadastrado com sucesso!', 'success')
        
        return redirect(url_for('admin'))
        
    except Exception as e:
        logging.error(f"Erro ao cadastrar local: {e}")
        flash('Erro ao cadastrar local. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/especialidade/<int:especialidade_id>/delete', methods=['POST'])
@requer_login_admin
def deletar_especialidade(especialidade_id):
    """Deletar uma especialidade"""
    try:
        especialidade = Especialidade.query.get_or_404(especialidade_id)
        
        # Verificar se há médicos usando esta especialidade
        medicos_usando = Medico.query.filter_by(especialidade_id=especialidade_id).count()
        if medicos_usando > 0:
            flash(f'Não é possível deletar "{especialidade.nome}" pois existem {medicos_usando} médico(s) cadastrado(s) nesta especialidade.', 'error')
            return redirect(url_for('admin'))
        
        # Verificar se há agendamentos usando esta especialidade
        agendamentos_usando = Agendamento.query.filter_by(especialidade_id=especialidade_id).count()
        if agendamentos_usando > 0:
            flash(f'Não é possível deletar "{especialidade.nome}" pois existem {agendamentos_usando} agendamento(s) registrado(s) nesta especialidade.', 'error')
            return redirect(url_for('admin'))
        
        nome_especialidade = especialidade.nome
        db.session.delete(especialidade)
        db.session.commit()
        
        flash(f'Especialidade "{nome_especialidade}" deletada com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao deletar especialidade: {e}")
        flash('Erro ao deletar especialidade. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/medico/<int:medico_id>/delete', methods=['POST'])
@requer_login_admin
def deletar_medico(medico_id):
    """Deletar um médico"""
    try:
        medico = Medico.query.get_or_404(medico_id)
        
        # Verificar se há agendamentos futuros para este médico
        from datetime import date
        agendamentos_futuros = Agendamento.query.filter_by(
            medico_id=medico_id,
            status='agendado'
        ).filter(Agendamento.data >= date.today()).count()
        
        if agendamentos_futuros > 0:
            flash(f'Não é possível deletar "{medico.nome}" pois existem {agendamentos_futuros} agendamento(s) futuro(s) para este médico.', 'error')
            return redirect(url_for('admin'))
        
        nome_medico = medico.nome
        
        # Deletar horários disponíveis do médico
        HorarioDisponivel.query.filter_by(medico_id=medico_id).delete()
        
        # Deletar o médico
        db.session.delete(medico)
        db.session.commit()
        
        flash(f'Médico "{nome_medico}" deletado com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao deletar médico: {e}")
        flash('Erro ao deletar médico. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/medicos/<int:medico_id>/toggle-recorrencia', methods=['POST'])
@requer_login_admin
def toggle_agenda_recorrente(medico_id):
    """Toggle da agenda recorrente do médico"""
    try:
        medico = Medico.query.get_or_404(medico_id)
        medico.agenda_recorrente = not medico.agenda_recorrente
        db.session.commit()
        
        status = "ativada" if medico.agenda_recorrente else "desativada"
        
        return jsonify({
            'success': True, 
            'agenda_recorrente': medico.agenda_recorrente,
            'message': f'Agenda recorrente {status} com sucesso!'
        })
    
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao alterar agenda recorrente: {e}")
        return jsonify({'success': False, 'message': 'Erro interno do servidor'}), 500

@app.route('/admin/paciente/<int:paciente_id>/detalhes')
@requer_login_admin
def detalhes_paciente(paciente_id):
    """Obter detalhes completos de um paciente"""
    try:
        paciente = Paciente.query.get_or_404(paciente_id)
        
        # Gerar HTML dos detalhes do paciente
        html_content = f"""
        <div class="row">
            <div class="col-md-6">
                <h6 class="text-info mb-3">
                    <i class="bi bi-person-circle me-2"></i>Informações Pessoais
                </h6>
                <div class="mb-3">
                    <strong>Nome Completo:</strong><br>
                    <span class="text-muted">{paciente.nome}</span>
                </div>
                <div class="mb-3">
                    <strong>CPF:</strong><br>
                    <code>{paciente.cpf}</code>
                </div>
                {'<div class="mb-3"><strong>Data de Nascimento:</strong><br><span class="text-muted">' + paciente.data_nascimento.strftime('%d/%m/%Y') + '</span></div>' if paciente.data_nascimento else ''}
                {'<div class="mb-3"><strong>Telefone:</strong><br><span class="text-success"><i class="bi bi-phone me-1"></i>' + paciente.telefone + '</span></div>' if paciente.telefone else ''}
                {'<div class="mb-3"><strong>Email:</strong><br><span class="text-info"><i class="bi bi-envelope me-1"></i>' + paciente.email + '</span></div>' if paciente.email else ''}
            </div>
            <div class="col-md-6">
                <h6 class="text-info mb-3">
                    <i class="bi bi-calendar-check me-2"></i>Estatísticas de Agendamentos
                </h6>
                <div class="mb-3">
                    <strong>Total de Agendamentos:</strong><br>
                    <span class="badge bg-primary fs-6">{len(paciente.agendamentos)}</span>
                </div>
                <div class="mb-3">
                    <strong>Agendamentos Futuros:</strong><br>
                    <span class="badge bg-success fs-6">{len([a for a in paciente.agendamentos if a.status == 'agendado'])}</span>
                </div>
                <div class="mb-3">
                    <strong>Agendamentos Concluídos:</strong><br>
                    <span class="badge bg-info fs-6">{len([a for a in paciente.agendamentos if a.status == 'concluido'])}</span>
                </div>
                <div class="mb-3">
                    <strong>Agendamentos Cancelados:</strong><br>
                    <span class="badge bg-warning fs-6">{len([a for a in paciente.agendamentos if a.status == 'cancelado'])}</span>
                </div>
            </div>
        </div>
        """
        
        return jsonify({
            'success': True,
            'html': html_content
        })
    
    except Exception as e:
        logging.error(f"Erro ao buscar detalhes do paciente: {e}")
        return jsonify({'success': False, 'message': 'Erro interno'}), 500

@app.route('/admin/paciente/<int:paciente_id>/historico')
@requer_login_admin
def historico_paciente(paciente_id):
    """Obter histórico completo de agendamentos de um paciente"""
    try:
        paciente = Paciente.query.get_or_404(paciente_id)
        agendamentos = sorted(paciente.agendamentos, key=lambda x: x.data, reverse=True)
        
        # Gerar HTML do histórico
        html_content = f"""
        <div class="mb-4">
            <h6 class="text-primary">
                <i class="bi bi-person-circle me-2"></i>{paciente.nome}
                <small class="text-muted">CPF: {paciente.cpf}</small>
            </h6>
        </div>
        
        {'<div class="alert alert-info"><i class="bi bi-info-circle me-2"></i>Este paciente não possui agendamentos registrados.</div>' if not agendamentos else ''}
        """
        
        if agendamentos:
            html_content += """
            <div class="table-responsive">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>Data/Hora</th>
                            <th>Especialidade</th>
                            <th>Médico</th>
                            <th>Status</th>
                            <th>Observações</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for agendamento in agendamentos:
                status_badges = {
                    'agendado': 'bg-success',
                    'concluido': 'bg-info',
                    'cancelado': 'bg-warning',
                    'ausente': 'bg-danger'
                }
                badge_class = status_badges.get(agendamento.status, 'bg-secondary')
                
                html_content += f"""
                <tr>
                    <td>
                        <strong>{agendamento.data.strftime('%d/%m/%Y')}</strong><br>
                        <small class="text-muted">{agendamento.hora.strftime('%H:%M')}</small>
                    </td>
                    <td>
                        <i class="bi bi-heart-pulse text-danger me-1"></i>
                        {agendamento.especialidade_rel.nome if agendamento.especialidade_rel else 'N/A'}
                    </td>
                    <td>
                        <i class="bi bi-person-badge text-info me-1"></i>
                        Dr(a). {agendamento.medico_rel.nome if agendamento.medico_rel else 'N/A'}
                    </td>
                    <td>
                        <span class="badge {badge_class}">{agendamento.status.title()}</span>
                    </td>
                    <td>
                        <small class="text-muted">{agendamento.observacoes or 'Nenhuma observação'}</small>
                    </td>
                </tr>
                """
            
            html_content += """
                    </tbody>
                </table>
            </div>
            """
        
        return jsonify({
            'success': True,
            'html': html_content
        })
    
    except Exception as e:
        logging.error(f"Erro ao buscar histórico do paciente: {e}")
        return jsonify({'success': False, 'message': 'Erro interno'}), 500

@app.route('/admin/local/<int:local_id>/edit', methods=['GET'])
@requer_login_admin
def editar_local(local_id):
    """Página para editar local específico"""
    local = Local.query.get_or_404(local_id)
    return render_template('editar_local.html', local=local)

@app.route('/admin/local/<int:local_id>/delete', methods=['POST'])
@requer_login_admin
def deletar_local(local_id):
    """Deletar um local"""
    try:
        local = Local.query.get_or_404(local_id)
        
        # Verificar se há agendamentos futuros para este local
        from datetime import date
        agendamentos_futuros = Agendamento.query.filter_by(
            local_id=local_id,
            status='agendado'
        ).filter(Agendamento.data >= date.today()).count()
        
        if agendamentos_futuros > 0:
            flash(f'Não é possível deletar "{local.nome}" pois existem {agendamentos_futuros} agendamento(s) futuro(s) para este local.', 'error')
            return redirect(url_for('admin'))
        
        # Verificar se há horários disponíveis para este local
        horarios_usando = HorarioDisponivel.query.filter_by(local_id=local_id).count()
        if horarios_usando > 0:
            flash(f'Não é possível deletar "{local.nome}" pois existem {horarios_usando} horário(s) configurado(s) neste local.', 'error')
            return redirect(url_for('admin'))
        
        nome_local = local.nome
        db.session.delete(local)
        db.session.commit()
        
        flash(f'Local "{nome_local}" deletado com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao deletar local: {e}")
        flash('Erro ao deletar local. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/horario/<int:horario_id>/delete', methods=['POST'])
@requer_login_admin
def deletar_horario(horario_id):
    """Deletar um horário"""
    try:
        horario = HorarioDisponivel.query.get_or_404(horario_id)
        
        medico_nome = horario.medico_rel.nome if horario.medico_rel else 'N/A'
        dia_nome = horario.get_dia_semana_nome()
        
        db.session.delete(horario)
        db.session.commit()
        
        flash(f'Horário de {medico_nome} ({dia_nome}) deletado com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao deletar horário: {e}")
        flash('Erro ao deletar horário. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/zerar-banco', methods=['POST'])
@requer_login_admin
def zerar_banco_dados():
    """Zerar completamente o banco de dados - AÇÃO PERIGOSA"""
    try:
        # Verificar confirmação de segurança
        confirmacao = request.form.get('confirmacao', '').strip()
        if confirmacao != 'APAGAR':
            flash('Operação cancelada. Confirmação inválida.', 'error')
            return redirect(url_for('admin_config'))
        
        # Contar dados antes de apagar
        total_agendamentos = Agendamento.query.count()
        total_pacientes = Paciente.query.count()
        total_medicos = Medico.query.count()
        total_conversas = Conversa.query.count()
        total_horarios = HorarioDisponivel.query.count()
        total_agend_recorrentes = AgendamentoRecorrente.query.count()
        
        # DELETAR TODOS OS DADOS (ordem importa devido às chaves estrangeiras)
        
        # 1. Agendamentos recorrentes
        AgendamentoRecorrente.query.delete()
        
        # 2. Agendamentos
        Agendamento.query.delete()
        
        # 3. Conversas (dependem de pacientes)
        Conversa.query.delete()
        
        # 4. Horários disponíveis (dependem de médicos e locais)
        HorarioDisponivel.query.delete()
        
        # 5. Pacientes
        Paciente.query.delete()
        
        # 6. Médicos (dependem de especialidades)
        Medico.query.delete()
        
        # 7. Especialidades
        Especialidade.query.delete()
        
        # 8. Locais
        Local.query.delete()
        
        # 9. Configurações (manter algumas básicas)
        # Não deletar todas as configurações para manter o sistema funcional
        
        # Commit das alterações
        db.session.commit()
        
        logging.warning(f"BANCO DE DADOS ZERADO! Dados removidos: {total_agendamentos} agendamentos, {total_pacientes} pacientes, {total_medicos} médicos, {total_conversas} conversas, {total_horarios} horários, {total_agend_recorrentes} agend. recorrentes")
        
        flash(f'🗑️ Banco de dados zerado com sucesso!\n\nDados removidos:\n- {total_agendamentos} agendamentos\n- {total_pacientes} pacientes\n- {total_medicos} médicos\n- {total_conversas} conversas\n- {total_horarios} horários\n- {total_agend_recorrentes} agendamentos recorrentes', 'success')
        
        return redirect(url_for('admin_config'))
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao zerar banco de dados: {e}")
        flash('Erro ao zerar banco de dados. Operação cancelada por segurança.', 'error')
        return redirect(url_for('admin_config'))

@app.route('/api/status')
def api_status():
    """Endpoint de status da API"""
    total_agendamentos = Agendamento.query.count()
    agendamentos_hoje = Agendamento.query.filter_by(
        data=date.today(),
        status='agendado'
    ).count()
    total_pacientes = Paciente.query.count()
    
    return jsonify({
        'status': 'ativo',
        'desenvolvedor': 'João Layon',
        'versao': '2.0.0 - Chatbot Avançado',
        'total_agendamentos': total_agendamentos,
        'agendamentos_hoje': agendamentos_hoje,
        'total_pacientes': total_pacientes,
        'especialidades': Especialidade.query.filter_by(ativo=True).count(),
        'preco_mensal': 'R$ 19,90'
    })


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)