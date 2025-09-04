import os
import logging
import uuid
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_file
from datetime import datetime, date, time
import json

# Importar novos modelos SQLite
from models_sqlite import (
    Paciente, Local, Especialidade, Medico, HorarioDisponivel, 
    Agendamento, Conversa, Configuracao, AgendamentoRecorrente
)

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

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-joao-layon-2025")

# Configurar para funcionar atrás de proxy (Replit)
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Importar serviço de AI
from ai_service_sqlite import chatbot_service

@app.route('/')
def index():
    """Página principal do chatbot"""
    return render_template('chat.html')

@app.route('/agendamentos')
def listar_agendamentos():
    """Lista todos os agendamentos (apenas administradores)"""
    # Esta página é apenas para administradores
    # Em uma implementação real, você adicionaria autenticação aqui
    agendamentos = Agendamento.find_all()
    # Ordenar por data e hora
    agendamentos.sort(key=lambda a: (a.data or '9999-12-31', a.hora or '00:00'))
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
        conversa = Conversa.find_by_session(session_id)
        if not conversa:
            conversa = Conversa.create(session_id=session_id, estado='inicio')
        
        # Atualizar timestamp da conversa
        conversa.atualizado_em = datetime.utcnow().isoformat()
        conversa.save()
        
        # Limpeza proativa de sessões abandonadas (5% das vezes)
        import random
        if random.randint(1, 20) == 1:
            try:
                from datetime import timedelta
                data_limite = (datetime.utcnow() - timedelta(hours=6)).isoformat()
                # Buscar conversas antigas para limpeza
                query = "SELECT * FROM conversas WHERE atualizado_em < ? AND estado != 'finalizado' LIMIT 5"
                from database import db
                rows = db.execute_query(query, (data_limite,))
                
                if rows:
                    # Deletar conversas antigas
                    for row in rows:
                        conversa_antiga = Conversa(**dict(row))
                        conversa_antiga.delete()
                    logger.info(f"Limpeza: {len(rows)} conversas abandonadas removidas")
            except Exception as cleanup_error:
                logger.warning(f"Erro na limpeza: {cleanup_error}")
        
        # Processar mensagem com IA
        resposta = chatbot_service.processar_mensagem(mensagem, conversa)
        
        # MELHORIA: Adicionar timestamp para cache busting em horários
        if resposta.get('tipo') in ['horarios', 'horarios_atualizados']:
            resposta['timestamp'] = datetime.utcnow().isoformat()
            resposta['cache_key'] = f"horarios_{datetime.utcnow().timestamp()}"
        
        # Salvar mudanças na conversa
        conversa.save()
        
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
    especialidades = Especialidade.find_active()
    return jsonify([esp.to_dict() for esp in especialidades])

@app.route('/locais')
def listar_locais():
    """API para listar locais ativos"""
    locais = Local.find_active()
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
        from database import db
        query = """
            SELECT * FROM agendamentos 
            WHERE medico_id = ? AND data = ? AND hora = ? AND status = 'agendado'
        """
        rows = db.execute_query(query, (medico_id, data_str, hora_str))
        
        if rows:
            return jsonify({
                'disponivel': False, 
                'motivo': 'Horário já ocupado por outro paciente',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Verificar agendamento recorrente
        dia_semana = data_agendamento.weekday()
        query_recorrente = """
            SELECT * FROM agendamentos_recorrentes 
            WHERE medico_id = ? AND dia_semana = ? AND hora = ? AND ativo = 1
            AND data_inicio <= ? AND (data_fim IS NULL OR data_fim >= ?)
        """
        rows_recorrentes = db.execute_query(query_recorrente, 
                                          (medico_id, dia_semana, hora_str, data_str, data_str))
        
        if rows_recorrentes:
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
        agendamento = Agendamento.find_by_id(agendamento_id)
        if not agendamento:
            flash('Agendamento não encontrado.', 'error')
            return redirect(url_for('listar_agendamentos'))
        
        agendamento.cancelar('Cancelado pela administração')
        
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
    especialidades = Especialidade.find_all()
    medicos = Medico.find_all()
    locais = Local.find_all()
    horarios_disponiveis = HorarioDisponivel.find_all()
    pacientes = Paciente.find_all()
    
    # Agrupar horários por médico para melhor visualização
    horarios_agrupados = {}
    for horario in horarios_disponiveis:
        medico = horario.get_medico()
        medico_nome = medico.nome if medico else 'Médico não encontrado'
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
    total_pacientes = len(pacientes)
    agendamentos_todos = Agendamento.find_all()
    total_agendamentos = len(agendamentos_todos)
    agendamentos_hoje = len(Agendamento.find_active_for_today())
    total_especialidades = len(Especialidade.find_active())
    
    # Stats por especialidade para relatórios
    agendamentos_por_especialidade = []
    for esp in especialidades:
        agendamentos_esp = [a for a in agendamentos_todos if a.especialidade_id == esp.id]
        total = len(agendamentos_esp)
        agendados = len([a for a in agendamentos_esp if a.status == 'agendado'])
        concluidos = len([a for a in agendamentos_esp if a.status == 'concluido'])
        cancelados = len([a for a in agendamentos_esp if a.status == 'cancelado'])
        
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
        agendamentos_paciente = [a for a in agendamentos_todos if a.paciente_id == paciente.id]
        especialidades_ids = list(set([a.especialidade_id for a in agendamentos_paciente]))
        
        if especialidades_ids:  # Só incluir pacientes que têm agendamentos
            especialidades_nomes = []
            for esp_id in especialidades_ids:
                esp = Especialidade.find_by_id(esp_id)
                if esp:
                    especialidades_nomes.append(esp.nome)
            
            pacientes_especialidades.append({
                'nome': paciente.nome,
                'cpf': paciente.cpf,
                'especialidades': especialidades_nomes,
                'total_agendamentos': len(agendamentos_paciente)
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
    
    return render_template('admin_config.html', configuracoes=configuracoes, locais=Local.find_all())

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
        existe = Especialidade.find_one_where({'nome': nome})
        if existe:
            flash('Especialidade já existe.', 'error')
            return redirect(url_for('admin'))
        
        Especialidade.create(nome=nome, descricao=descricao if descricao else None)
        
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
        especialidade_id = request.form.get('especialidade_id', '').strip()
        
        if not all([nome, crm, especialidade_id]):
            flash('Todos os campos são obrigatórios.', 'error')
            return redirect(url_for('admin'))
        
        # Verificar se CRM já existe
        existe = Medico.find_one_where({'crm': crm})
        if existe:
            flash('CRM já cadastrado.', 'error')
            return redirect(url_for('admin'))
        
        # Verificar se especialidade existe
        especialidade = Especialidade.find_by_id(int(especialidade_id))
        if not especialidade:
            flash('Especialidade não encontrada.', 'error')
            return redirect(url_for('admin'))
        
        Medico.create(nome=nome, crm=crm, especialidade_id=int(especialidade_id))
        
        flash(f'Médico "{nome}" cadastrado com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        logging.error(f"Erro ao cadastrar médico: {e}")
        flash('Erro ao cadastrar médico. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/locais', methods=['POST'])
@requer_login_admin
def admin_locais():
    """Cadastrar novo local"""
    try:
        nome = request.form.get('nome', '').strip()
        endereco = request.form.get('endereco', '').strip()
        cidade = request.form.get('cidade', '').strip()
        telefone = request.form.get('telefone', '').strip()
        
        if not nome:
            flash('Nome do local é obrigatório.', 'error')
            return redirect(url_for('admin'))
        
        # Verificar se já existe
        existe = Local.find_one_where({'nome': nome})
        if existe:
            flash('Local já existe.', 'error')
            return redirect(url_for('admin'))
        
        Local.create(
            nome=nome,
            endereco=endereco if endereco else None,
            cidade=cidade if cidade else None,
            telefone=telefone if telefone else None
        )
        
        flash(f'Local "{nome}" cadastrado com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        logging.error(f"Erro ao cadastrar local: {e}")
        flash('Erro ao cadastrar local. Tente novamente.', 'error')
        return redirect(url_for('admin'))

@app.route('/admin/horarios', methods=['POST'])
@requer_login_admin
def admin_horarios():
    """Cadastrar novo horário disponível"""
    try:
        medico_id = request.form.get('medico_id', '').strip()
        local_id = request.form.get('local_id', '').strip()
        dia_semana = request.form.get('dia_semana', '').strip()
        hora_inicio = request.form.get('hora_inicio', '').strip()
        hora_fim = request.form.get('hora_fim', '').strip()
        duracao_consulta = request.form.get('duracao_consulta', '30').strip()
        
        if not all([medico_id, local_id, dia_semana, hora_inicio, hora_fim]):
            flash('Todos os campos são obrigatórios.', 'error')
            return redirect(url_for('admin'))
        
        HorarioDisponivel.create(
            medico_id=int(medico_id),
            local_id=int(local_id),
            dia_semana=int(dia_semana),
            hora_inicio=hora_inicio,
            hora_fim=hora_fim,
            duracao_consulta=int(duracao_consulta)
        )
        
        flash('Horário cadastrado com sucesso!', 'success')
        return redirect(url_for('admin'))
        
    except Exception as e:
        logging.error(f"Erro ao cadastrar horário: {e}")
        flash('Erro ao cadastrar horário. Tente novamente.', 'error')
        return redirect(url_for('admin'))

# Log de sistema ativo (para debug) - Removido before_first_request depreciado
def log_sistema_ativo():
    """Log quando o sistema ficar ativo"""
    logger.info("Sistema João Layon Ativo: SQLite3 Version")
    stats = {
        'status': 'ativo',
        'versao': '2.0.0 - SQLite3 Pure',
        'desenvolvedor': 'João Layon',
        'preco_mensal': 'R$ 19,90',
        'total_pacientes': len(Paciente.find_all()),
        'total_agendamentos': len(Agendamento.find_all()),
        'agendamentos_hoje': len(Agendamento.find_active_for_today()),
        'especialidades': len(Especialidade.find_active())
    }
    print("Sistema João Layon Ativo:", stats)

# Executar log no carregamento do módulo
log_sistema_ativo()

# Rota para testar JavaScript console logs
@app.route('/log-test')
def log_test():
    """Rota para testar logs no console JavaScript"""
    stats = {
        'status': 'ativo',
        'versao': '2.0.0 - SQLite3 Pure',
        'desenvolvedor': 'João Layon',
        'preco_mensal': 'R$ 19,90',
        'total_pacientes': len(Paciente.find_all()),
        'total_agendamentos': len(Agendamento.find_all()),
        'agendamentos_hoje': len(Agendamento.find_active_for_today()),
        'especialidades': len(Especialidade.find_active())
    }
    
    html = f"""
    <script>
    console.log("Sistema João Layon Ativo:", {json.dumps(stats)});
    </script>
    <h1>Sistema Ativo - SQLite3</h1>
    <pre>{json.dumps(stats, indent=2)}</pre>
    """
    return html

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)