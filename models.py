from app import db
from datetime import datetime, date, time
import json

class Paciente(db.Model):
    """Modelo para pacientes da clínica"""
    __tablename__ = 'pacientes'
    
    id = db.Column(db.Integer, primary_key=True)
    cpf = db.Column(db.String(11), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    data_nascimento = db.Column(db.Date)  # Data de nascimento do paciente
    telefone = db.Column(db.String(15))
    email = db.Column(db.String(120))
    carteirinha = db.Column(db.String(50))  # Número da carteirinha do plano
    tipo_atendimento = db.Column(db.String(20), default='particular')  # 'plano' ou 'particular'
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    agendamentos = db.relationship('Agendamento', backref='paciente_rel', lazy=True)
    conversas = db.relationship('Conversa', backref='paciente_rel', lazy=True)
    
    def __repr__(self):
        return f'<Paciente {self.nome} - {self.cpf}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'cpf': self.cpf,
            'nome': self.nome,
            'data_nascimento': self.data_nascimento.strftime('%d/%m/%Y') if self.data_nascimento else None,
            'telefone': self.telefone,
            'email': self.email,
            'carteirinha': self.carteirinha,
            'tipo_atendimento': self.tipo_atendimento
        }

class Local(db.Model):
    """Modelo para locais de atendimento"""
    __tablename__ = 'locais'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    endereco = db.Column(db.String(200))
    cidade = db.Column(db.String(100))
    telefone = db.Column(db.String(15))
    ativo = db.Column(db.Boolean, default=True)
    
    # Relacionamentos
    horarios = db.relationship('HorarioDisponivel', backref='local_rel', lazy=True)
    agendamentos = db.relationship('Agendamento', backref='local_rel', lazy=True)
    
    def __repr__(self):
        return f'<Local {self.nome} - {self.cidade}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'endereco': self.endereco,
            'cidade': self.cidade,
            'telefone': self.telefone
        }

class Especialidade(db.Model):
    """Modelo para especialidades médicas"""
    __tablename__ = 'especialidades'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    descricao = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True)
    
    # Relacionamentos
    medicos = db.relationship('Medico', backref='especialidade_rel', lazy=True)
    agendamentos = db.relationship('Agendamento', backref='especialidade_rel', lazy=True)
    
    def __repr__(self):
        return f'<Especialidade {self.nome}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao
        }

class Medico(db.Model):
    """Modelo para médicos da clínica"""
    __tablename__ = 'medicos'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    crm = db.Column(db.String(20), unique=True)
    especialidade_id = db.Column(db.Integer, db.ForeignKey('especialidades.id'), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    agenda_recorrente = db.Column(db.Boolean, default=False)  # Checkbox para agenda fixa semanal
    
    # Relacionamentos
    agendamentos = db.relationship('Agendamento', backref='medico_rel', lazy=True)
    horarios = db.relationship('HorarioDisponivel', backref='medico_rel', lazy=True)
    
    def __repr__(self):
        return f'<Medico {self.nome} - {self.crm}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'crm': self.crm,
            'especialidade_id': self.especialidade_id
        }

class HorarioDisponivel(db.Model):
    """Modelo para horários disponíveis dos médicos"""
    __tablename__ = 'horarios_disponiveis'
    
    id = db.Column(db.Integer, primary_key=True)
    medico_id = db.Column(db.Integer, db.ForeignKey('medicos.id'), nullable=False)
    local_id = db.Column(db.Integer, db.ForeignKey('locais.id'), nullable=False)
    dia_semana = db.Column(db.Integer, nullable=False)  # 0=segunda, 6=domingo
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fim = db.Column(db.Time, nullable=False)
    duracao_consulta = db.Column(db.Integer, default=30)  # minutos
    ativo = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        medico_nome = self.medico_rel.nome if hasattr(self, 'medico_rel') and self.medico_rel else 'N/A'
        return f'<Horario {medico_nome} - {self.hora_inicio}-{self.hora_fim}>'
    
    def get_dia_semana_nome(self):
        """Retorna o nome do dia da semana"""
        dias = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        return dias[self.dia_semana] if 0 <= self.dia_semana < len(dias) else 'N/A'
    
    def to_dict(self):
        dias = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        medico_nome = self.medico_rel.nome if hasattr(self, 'medico_rel') and self.medico_rel else 'N/A'
        local_nome = self.local_rel.nome if hasattr(self, 'local_rel') and self.local_rel else 'N/A'
        return {
            'id': self.id,
            'medico': medico_nome,
            'local': local_nome,
            'dia_semana': dias[self.dia_semana],
            'hora_inicio': self.hora_inicio.strftime('%H:%M'),
            'hora_fim': self.hora_fim.strftime('%H:%M'),
            'duracao': self.duracao_consulta
        }

class Agendamento(db.Model):
    """Modelo para agendamentos médicos"""
    __tablename__ = 'agendamentos'
    
    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey('pacientes.id'), nullable=False)
    medico_id = db.Column(db.Integer, db.ForeignKey('medicos.id'), nullable=False)
    especialidade_id = db.Column(db.Integer, db.ForeignKey('especialidades.id'), nullable=False)
    local_id = db.Column(db.Integer, db.ForeignKey('locais.id'), nullable=False)
    data = db.Column(db.Date, nullable=False)
    hora = db.Column(db.Time, nullable=False)
    observacoes = db.Column(db.Text)
    status = db.Column(db.String(20), default='agendado')  # agendado, cancelado, concluido
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    cancelado_em = db.Column(db.DateTime)
    motivo_cancelamento = db.Column(db.String(255))
    
    def __repr__(self):
        paciente_nome = self.paciente_rel.nome if hasattr(self, 'paciente_rel') and self.paciente_rel else 'N/A'
        return f'<Agendamento {paciente_nome} - {self.data} {self.hora}>'
    
    def to_dict(self):
        paciente_nome = self.paciente_rel.nome if hasattr(self, 'paciente_rel') and self.paciente_rel else 'N/A'
        medico_nome = self.medico_rel.nome if hasattr(self, 'medico_rel') and self.medico_rel else 'N/A'
        especialidade_nome = self.especialidade_rel.nome if hasattr(self, 'especialidade_rel') and self.especialidade_rel else 'N/A'
        local_nome = self.local_rel.nome if hasattr(self, 'local_rel') and self.local_rel else 'N/A'
        return {
            'id': self.id,
            'paciente': paciente_nome,
            'medico': medico_nome,
            'especialidade': especialidade_nome,
            'local': local_nome,
            'data': self.data.strftime('%d/%m/%Y'),
            'hora': self.hora.strftime('%H:%M'),
            'observacoes': self.observacoes,
            'status': self.status,
            'criado_em': self.criado_em.strftime('%d/%m/%Y %H:%M')
        }

class Conversa(db.Model):
    """Modelo para manter estado das conversas do chatbot"""
    __tablename__ = 'conversas'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), nullable=False, unique=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey('pacientes.id'), nullable=True)
    estado = db.Column(db.String(50), default='inicio')  # inicio, aguardando_cpf, cadastro, especialidade, horarios, confirmacao
    dados_temporarios = db.Column(db.Text)  # JSON com dados da conversa
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Conversa {self.session_id} - {self.estado}>'
    
    def get_dados(self):
        """Retorna dados temporários como dicionário"""
        if self.dados_temporarios:
            return json.loads(self.dados_temporarios)
        return {}
    
    def set_dados(self, dados):
        """Define dados temporários a partir de dicionário"""
        self.dados_temporarios = json.dumps(dados)
    
    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'paciente_id': self.paciente_id,
            'estado': self.estado,
            'dados': self.get_dados(),
            'criado_em': self.criado_em.strftime('%d/%m/%Y %H:%M')
        }

class Configuracao(db.Model):
    """Modelo para configurações do sistema"""
    __tablename__ = 'configuracoes'
    
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(100), nullable=False, unique=True)
    valor = db.Column(db.Text)
    descricao = db.Column(db.String(255))
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Configuracao {self.chave}: {self.valor}>'
    
    @staticmethod
    def get_valor(chave, padrao=None):
        """Obtém valor de uma configuração"""
        config = Configuracao.query.filter_by(chave=chave).first()
        return config.valor if config else padrao
    
    @staticmethod
    def set_valor(chave, valor, descricao=None):
        """Define valor de uma configuração"""
        config = Configuracao.query.filter_by(chave=chave).first()
        if config:
            config.valor = valor
            if descricao:
                config.descricao = descricao
        else:
            config = Configuracao(chave=chave, valor=valor, descricao=descricao)
            db.session.add(config)
        db.session.commit()
        return config

class AgendamentoRecorrente(db.Model):
    """Modelo para agendamentos recorrentes semanais"""
    __tablename__ = 'agendamentos_recorrentes'
    
    id = db.Column(db.Integer, primary_key=True)
    paciente_id = db.Column(db.Integer, db.ForeignKey('pacientes.id'), nullable=False)
    medico_id = db.Column(db.Integer, db.ForeignKey('medicos.id'), nullable=False)
    especialidade_id = db.Column(db.Integer, db.ForeignKey('especialidades.id'), nullable=False)
    local_id = db.Column(db.Integer, db.ForeignKey('locais.id'), nullable=False)
    dia_semana = db.Column(db.Integer, nullable=False)  # 0=segunda, 6=domingo
    hora = db.Column(db.Time, nullable=False)
    data_inicio = db.Column(db.Date, nullable=False)  # Quando começou a recorrência
    data_fim = db.Column(db.Date)  # Quando termina (null = indefinido)
    ativo = db.Column(db.Boolean, default=True)
    observacoes = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamentos serão criados automaticamente pelos foreign keys
    
    def __repr__(self):
        dias = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        dia_nome = dias[self.dia_semana] if 0 <= self.dia_semana < len(dias) else 'N/A'
        return f'<AgendamentoRecorrente ID:{self.id} - {dia_nome} {self.hora}>'
    
    def get_dia_semana_nome(self):
        """Retorna o nome do dia da semana"""
        dias = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
        return dias[self.dia_semana] if 0 <= self.dia_semana < len(dias) else 'N/A'
    
    def to_dict(self):
        return {
            'id': self.id,
            'paciente_id': self.paciente_id,
            'medico_id': self.medico_id,
            'especialidade_id': self.especialidade_id,
            'local_id': self.local_id,
            'dia_semana': self.get_dia_semana_nome(),
            'hora': self.hora.strftime('%H:%M'),
            'data_inicio': self.data_inicio.strftime('%d/%m/%Y'),
            'data_fim': self.data_fim.strftime('%d/%m/%Y') if self.data_fim else 'Indefinido',
            'observacoes': self.observacoes,
            'ativo': self.ativo
        }