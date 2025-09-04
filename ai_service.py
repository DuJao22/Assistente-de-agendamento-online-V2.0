import json
import os
import logging
from datetime import datetime, date, time, timedelta
import google.generativeai as genai

# Configurar cliente Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Verificar se a API key existe - OBRIGATÓRIA para funcionamento
if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY é obrigatória para o funcionamento do sistema de agendamento inteligente. Configure a chave da API do Google Gemini."
    )

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')


class ChatbotService:
    """Serviço de chatbot para agendamento médico usando Gemini"""

    def __init__(self):
        pass

    def processar_mensagem(self, mensagem, conversa):
        """
        Processa mensagem do usuário baseado no estado atual da conversa
        
        Args:
            mensagem (str): Mensagem do usuário
            conversa (Conversa): Objeto da conversa atual
            
        Returns:
            dict: Resposta do chatbot com próxima ação
        """
        try:
            estado = conversa.estado or 'inicio'
            dados = conversa.get_dados() or {}

            # Log para debug
            logging.info(f"Estado atual: {estado}, Mensagem: {mensagem}")

            # MELHORIA: Detectar cancelamento em qualquer estado (exceto já cancelando)
            if estado != 'cancelamento' and self._eh_cancelamento(mensagem):
                logging.info(
                    f"Cancelamento detectado, mudando estado de '{estado}' para 'cancelamento'"
                )
                conversa.estado = 'cancelamento'
                conversa.set_dados({})
                return self._processar_cancelamento(mensagem, conversa)

            # INTELIGÊNCIA MELHORADA: Verificar se é saudação em qualquer estado
            # Se for saudação, sempre resetar conversa para evitar estados inconsistentes
            if self._eh_saudacao(mensagem):
                logging.info(
                    f"Saudação detectada, resetando conversa do estado '{estado}' para 'inicio'"
                )
                conversa.estado = 'inicio'
                conversa.set_dados({})
                return self._processar_inicio(mensagem, conversa)

            if estado == 'inicio' or estado == 'finalizado':
                return self._processar_inicio(mensagem, conversa)
            elif estado == 'aguardando_cpf':
                return self._processar_cpf(mensagem, conversa)
            elif estado == 'cadastro':
                return self._processar_cadastro(mensagem, conversa, dados)
            elif estado == 'local':
                return self._processar_local(mensagem, conversa)
            elif estado == 'especialidade':
                return self._processar_especialidade(mensagem, conversa)
            elif estado == 'horarios':
                return self._processar_horarios(mensagem, conversa, dados)
            elif estado == 'confirmacao':
                return self._processar_confirmacao(mensagem, conversa, dados)
            elif estado == 'cancelamento':
                return self._processar_cancelamento(mensagem, conversa)
            elif estado == 'consulta_agendamentos':
                return self._processar_consulta_agendamentos(
                    mensagem, conversa)
            else:
                # Resetar estado para início
                conversa.estado = 'inicio'
                conversa.set_dados({})
                return self._processar_inicio(mensagem, conversa)

        except Exception as e:
            logging.error(f"Erro ao processar mensagem: {e}")
            # Resetar conversa em caso de erro
            conversa.estado = 'inicio'
            conversa.set_dados({})
            return self._resposta_erro(
                "Desculpe, ocorreu um erro. Vamos recomeçar o atendimento.")

    def _processar_inicio(self, mensagem, conversa):
        """Processa mensagem inicial e pede CPF"""
        mensagem_lower = mensagem.lower().strip()

        # Detectar tipo de mensagem - primeiro com regras simples, depois com IA se disponível
        tipo = self._detectar_tipo_mensagem(mensagem)

        if tipo == 'cancelamento':
            conversa.estado = 'cancelamento'
            return {
                'success': True,
                'message':
                "Olá! Para cancelar uma consulta, preciso do seu CPF. Digite apenas os números:",
                'tipo': 'texto',
                'proximo_estado': 'cancelamento'
            }
        elif tipo == 'consulta':
            conversa.estado = 'consulta_agendamentos'
            return {
                'success': True,
                'message':
                "Olá! Para consultar seus agendamentos, preciso do seu CPF. Digite apenas os números:",
                'tipo': 'texto',
                'proximo_estado': 'consulta_agendamentos'
            }
        elif tipo == 'informacao':
            # Obter informações dinâmicas das configurações
            from models import Configuracao, Local
            nome_clinica = Configuracao.get_valor('nome_clinica',
                                                  'Clínica João Layon')
            telefone = Configuracao.get_valor('telefone_clinica',
                                              '(31) 3333-4444')
            horario = Configuracao.get_valor('horario_funcionamento',
                                             'Segunda a Sexta, 8h às 18h')

            # Buscar locais ativos
            locais = Local.query.filter_by(ativo=True).all()
            locais_texto = "\n".join([
                f"• {local.nome} - {local.endereco or local.cidade}"
                for local in locais
            ])
            if not locais_texto:
                locais_texto = "• Informações em atualização"

            return {
                'success': True,
                'message':
                f"📋 **{nome_clinica} - Informações**\n\n🏥 **Locais de Atendimento:**\n{locais_texto}\n\n📞 **Contato:** {telefone}\n\n⏰ **Horário de Funcionamento:** {horario}\n\n💬 Este chatbot é específico para **agendamentos de consultas**. Para outras informações detalhadas, entre em contato pelo telefone da clínica.\n\n🩺 Digite 'agendar' para marcar uma consulta!",
                'tipo': 'info',
                'proximo_estado': 'inicio'
            }
        elif tipo == 'fora_escopo':
            # Obter informações dinâmicas das configurações
            from models import Configuracao
            nome_clinica = Configuracao.get_valor('nome_clinica',
                                                  'Clínica João Layon')
            nome_assistente = Configuracao.get_valor('nome_assistente',
                                                     'Assistente Virtual')
            telefone = Configuracao.get_valor('telefone_clinica',
                                              '(31) 3333-4444')

            return {
                'success': True,
                'message':
                f"🤖 Olá! Eu sou o **{nome_assistente}** da **{nome_clinica}**.\n\n📝 Este chatbot é especializado apenas em **agendamentos de consultas médicas**.\n\nPara outras dúvidas, informações ou assuntos não relacionados a agendamentos, entre em contato diretamente com nossa clínica:\n\n📞 **Telefone:** {telefone}\n\n🩺 Se você deseja agendar uma consulta, digite 'agendar' para começar!",
                'tipo': 'orientacao',
                'proximo_estado': 'inicio'
            }
        else:
            # Agendamento ou saudação normal
            conversa.estado = 'aguardando_cpf'
            return {
                'success': True,
                'message':
                "Olá! Bem-vindo ao sistema de agendamento da Clínica João Layon! 😊\n\n📄 Para começar o agendamento, preciso do CPF da pessoa que será atendida (o paciente).\n\nDigite apenas os 11 números do CPF:",
                'tipo': 'texto',
                'proximo_estado': 'aguardando_cpf'
            }

    def _detectar_tipo_mensagem(self, mensagem):
        """Detecta o tipo de mensagem com IA e fallback inteligente"""
        # FALLBACK 1: Regras básicas para casos críticos
        mensagem_lower = mensagem.lower().strip()

        # Palavras-chave para detecção básica
        if any(palavra in mensagem_lower for palavra in
               ['cancelar', 'desmarcar', 'remover consulta', 'cancelo']):
            return 'cancelamento'

        if any(palavra in mensagem_lower for palavra in [
                'meus agendamentos', 'minhas consultas',
                'consultar agendamento', 'ver consultas'
        ]):
            return 'consulta'

        if any(palavra in mensagem_lower for palavra in [
                'telefone', 'endereço', 'onde fica', 'horário funcionamento',
                'localização'
        ]):
            return 'informacao'

        if any(palavra in mensagem_lower for palavra in
               ['clima', 'tempo', 'futebol', 'política', 'receita culinária']):
            return 'fora_escopo'

        # FALLBACK 2: Tentar usar IA com tratamento robusto
        try:
            prompt = f"""
            Você é um assistente médico virtual especializado em agendamentos. Analise cuidadosamente a mensagem do usuário e classifique com máxima precisão.

            Mensagem do usuário: "{mensagem}"
            
            Classifique a mensagem em uma das categorias, considerando contexto, intenção e nuances:
            
            1. "agendamento" - Qualquer intenção de agendar consulta, marcar horário, saudações iniciais (oi, olá, boa tarde), pedidos de ajuda para marcar consulta, menções de sintomas ou necessidade médica
            
            2. "cancelamento" - Intenção clara de cancelar, desmarcar ou remover agendamento existente
            
            3. "consulta" - Quer verificar, ver, listar seus agendamentos ou consultas já marcadas
            
            4. "informacao" - Perguntas sobre a clínica (telefone, endereço, horários de funcionamento, médicos disponíveis, especialidades oferecidas, localização)
            
            5. "fora_escopo" - Conversas casuais não relacionadas à clínica, perguntas pessoais, assuntos não médicos ou de agendamento
            
            Exemplos:
            - "oi" → agendamento
            - "preciso de uma consulta" → agendamento  
            - "estou com dor de cabeça" → agendamento
            - "quero cancelar minha consulta" → cancelamento
            - "quais são meus agendamentos?" → consulta
            - "qual o telefone da clínica?" → informacao
            - "como está o tempo?" → fora_escopo
            
            Responda APENAS com uma palavra: agendamento, cancelamento, consulta, informacao, fora_escopo
            """

            response = model.generate_content(prompt)

            resultado = response.text.strip().lower(
            ) if response.text else "agendamento"

            # Validar resposta da IA
            if resultado in [
                    'agendamento', 'cancelamento', 'consulta', 'informacao',
                    'fora_escopo'
            ]:
                logging.info(
                    f"IA detectou tipo '{resultado}' para mensagem: '{mensagem}'"
                )
                return resultado
            else:
                logging.warning(
                    f"IA retornou valor inválido '{resultado}', usando fallback"
                )
                return 'agendamento'  # Fallback padrão

        except Exception as e:
            logging.warning(
                f"IA temporariamente indisponível: {e}. Usando fallback inteligente."
            )

            # FALLBACK 3: Lógica heurística avançada
            # Saudações e sintomas -> agendamento
            if any(palavra in mensagem_lower for palavra in [
                    'oi', 'olá', 'ola', 'bom dia', 'boa tarde', 'boa noite',
                    'hello', 'hi', 'dor', 'problema', 'consulta', 'médico',
                    'doutor', 'sintoma', 'doença', 'preciso', 'quero marcar',
                    'agendar', 'emergência'
            ]):
                return 'agendamento'

            # Se nada se encaixar, assumir agendamento (mais seguro)
            return 'agendamento'

    def _processar_cpf(self, mensagem, conversa):
        """Processa CPF e verifica se existe no sistema"""
        # Extrair CPF da mensagem
        cpf = self._extrair_cpf(mensagem)

        if not cpf:
            return {
                'success': False,
                'message':
                "CPF inválido. Por favor, digite apenas os 11 números do CPF:",
                'tipo': 'texto',
                'proximo_estado': 'aguardando_cpf'
            }

        # Verificar se paciente existe
        from models import Paciente
        paciente = Paciente.query.filter_by(cpf=cpf).first()

        # Verificar o que o usuário quer fazer baseado no estado anterior
        dados_temp = conversa.get_dados() or {}
        acao_desejada = dados_temp.get('acao_desejada', 'agendar')

        if paciente:
            # Paciente já existe - direcionar conforme a ação
            conversa.paciente_id = paciente.id
            dados = {
                'cpf': cpf,
                'paciente_id': paciente.id,
                'acao_desejada': acao_desejada
            }
            conversa.set_dados(dados)

            # Verificar qual ação o usuário quer fazer
            mensagem_anterior = dados_temp.get('mensagem_inicial', '').lower()

            if 'cancelar' in mensagem_anterior or conversa.estado == 'cancelamento':
                return self._processar_cancelamento_cpf_valido(
                    conversa, paciente)
            elif 'consultar' in mensagem_anterior or conversa.estado == 'consulta_agendamentos':
                return self._processar_consulta_agendamentos_cpf_valido(
                    conversa, paciente)
            else:
                # Agendar consulta - primeiro perguntar o local
                conversa.estado = 'local'
                return {
                    'success': True,
                    'message':
                    f"Olá, {paciente.nome}! 👋\n\nPrimeiro, em qual local você gostaria de ser atendido?",
                    'tipo': 'locais',
                    'proximo_estado': 'local'
                }
        else:
            # Novo paciente - só permite agendamento, não consulta/cancelamento
            if conversa.estado in ['cancelamento', 'consulta_agendamentos']:
                return {
                    'success': False,
                    'message':
                    f"CPF {self._formatar_cpf(cpf)} não encontrado no sistema. Para cancelar ou consultar agendamentos, é necessário ter cadastro.\n\nDigite 'oi' para fazer um novo agendamento.",
                    'tipo': 'texto',
                    'proximo_estado': 'inicio'
                }

            # Novo paciente - precisa cadastrar para agendar
            conversa.estado = 'cadastro'
            dados = {'cpf': cpf, 'etapa_cadastro': 'nome'}
            conversa.set_dados(dados)

            return {
                'success': True,
                'message':
                f"CPF {self._formatar_cpf(cpf)} não encontrado.\n\nVamos fazer seu cadastro! Qual é o seu nome completo?",
                'tipo': 'texto',
                'proximo_estado': 'cadastro'
            }

    def _processar_cadastro(self, mensagem, conversa, dados):
        """Processa cadastro de novo paciente"""
        etapa = dados.get('etapa_cadastro', 'nome')

        if etapa == 'nome':
            dados['nome'] = mensagem.strip()
            dados['etapa_cadastro'] = 'data_nascimento'
            conversa.set_dados(dados)

            return {
                'success': True,
                'message':
                f"Prazer, {dados['nome']}! \n\nAgora preciso da data de nascimento do paciente no formato DD/MM/AAAA (ex: 15/03/1990):",
                'tipo': 'texto',
                'proximo_estado': 'cadastro'
            }

        elif etapa == 'data_nascimento':
            try:
                # Validar e converter data de nascimento
                data_str = mensagem.strip()
                data_nascimento = self._validar_data_nascimento(data_str)
                if not data_nascimento:
                    return {
                        'success': False,
                        'message':
                        "Data inválida. Digite a data de nascimento no formato DD/MM/AAAA (ex: 15/03/1990):",
                        'tipo': 'texto',
                        'proximo_estado': 'cadastro'
                    }

                # Converter data para string para serialização JSON
                dados['data_nascimento'] = data_nascimento.strftime('%Y-%m-%d')
                dados['etapa_cadastro'] = 'telefone'
                logging.info(
                    f"Data armazenada nos dados: {dados['data_nascimento']}")
                conversa.set_dados(dados)

                return {
                    'success': True,
                    'message':
                    "Perfeito! Agora preciso do telefone de contato com DDD (ex: 11999887766):",
                    'tipo': 'texto',
                    'proximo_estado': 'cadastro'
                }
            except Exception as e:
                return {
                    'success': False,
                    'message':
                    "Data inválida. Digite a data de nascimento no formato DD/MM/AAAA (ex: 15/03/1990):",
                    'tipo': 'texto',
                    'proximo_estado': 'cadastro'
                }

        elif etapa == 'telefone':
            telefone = self._extrair_telefone(mensagem)
            if not telefone:
                return {
                    'success': False,
                    'message':
                    "Telefone inválido. Digite o telefone com DDD (ex: 11999887766):",
                    'tipo': 'texto',
                    'proximo_estado': 'cadastro'
                }

            dados['telefone'] = telefone
            dados['etapa_cadastro'] = 'email'
            conversa.set_dados(dados)

            return {
                'success': True,
                'message':
                "Perfeito! Agora seu e-mail (opcional - digite 'pular' se não quiser informar):",
                'tipo': 'texto',
                'proximo_estado': 'cadastro'
            }

        elif etapa == 'email':
            email = None
            if mensagem.strip().lower() not in ['pular', 'não', 'nao']:
                email = self._extrair_email(mensagem)
                if not email and mensagem.strip().lower() not in [
                        'pular', 'não', 'nao'
                ]:
                    return {
                        'success': False,
                        'message':
                        "E-mail inválido. Digite um e-mail válido ou 'pular' para continuar:",
                        'tipo': 'texto',
                        'proximo_estado': 'cadastro'
                    }

            dados['email'] = email
            dados['etapa_cadastro'] = 'carteirinha'
            conversa.set_dados(dados)

            return {
                'success': True,
                'message':
                "Você tem plano de saúde? Se sim, digite o número da sua carteirinha.\nSe não tem plano ou prefere atendimento particular, digite 'particular':",
                'tipo': 'texto',
                'proximo_estado': 'cadastro'
            }

        elif etapa == 'carteirinha':
            carteirinha = None
            tipo_atendimento = 'particular'

            mensagem_lower = mensagem.strip().lower()
            if mensagem_lower not in [
                    'particular', 'nao', 'não', 'sem plano', 'pular'
            ]:
                # Validar se é um número de carteirinha válido
                carteirinha_limpa = ''.join(c for c in mensagem if c.isalnum())
                if len(carteirinha_limpa
                       ) >= 6:  # Mínimo 6 caracteres para carteirinha
                    carteirinha = carteirinha_limpa[:
                                                    50]  # Limitar a 50 caracteres
                    tipo_atendimento = 'plano'
                else:
                    return {
                        'success': False,
                        'message':
                        "Número de carteirinha inválido. Digite um número válido ou 'particular' para atendimento particular:",
                        'tipo': 'texto',
                        'proximo_estado': 'cadastro'
                    }

            dados['carteirinha'] = carteirinha
            dados['tipo_atendimento'] = tipo_atendimento

            # Criar paciente no banco
            from models import Paciente
            from app import db

            novo_paciente = Paciente(
                cpf=dados['cpf'],
                nome=dados['nome'],
                data_nascimento=dados.get('data_nascimento'),
                telefone=dados['telefone'],
                email=dados.get('email'),
                carteirinha=dados.get('carteirinha'),
                tipo_atendimento=dados.get('tipo_atendimento', 'particular'))

            # Salvar novo paciente com transação segura
            try:
                db.session.add(novo_paciente)
                db.session.commit()
                conversa.paciente_id = novo_paciente.id
            except Exception as e:
                db.session.rollback()
                logging.error(f"Erro ao salvar paciente: {e}")
                return {
                    'success': False,
                    'message':
                    'Erro interno ao cadastrar paciente. Tente novamente.',
                    'tipo': 'erro',
                    'proximo_estado': 'inicio'
                }
            conversa.estado = 'local'
            dados['paciente_id'] = novo_paciente.id
            conversa.set_dados(dados)

            # Mensagem personalizada baseada no tipo de atendimento
            tipo_msg = "plano de saúde 💳" if dados.get(
                'tipo_atendimento') == 'plano' else "atendimento particular 💰"

            return {
                'success': True,
                'message':
                f"Cadastro realizado com sucesso, {dados['nome']}! 🎉\n\n📄 Tipo: {tipo_msg}\n\nPrimeiro, em qual local você gostaria de ser atendido?",
                'tipo': 'locais',
                'proximo_estado': 'local'
            }

    def _processar_local(self, mensagem, conversa):
        """Processa seleção de local de atendimento usando IA AVANÇADA"""
        from models import Local, Especialidade, HorarioDisponivel

        # Buscar locais ativos
        locais = Local.query.filter_by(ativo=True).all()
        locais_info = [f"{local.nome} em {local.cidade}" for local in locais]
        locais_disponiveis = [{
            'id': local.id,
            'nome': local.nome,
            'cidade': local.cidade
        } for local in locais]

        try:
            prompt = f"""
            Você é um assistente médico especializado. O usuário está escolhendo um local para atendimento.

            Mensagem do usuário: "{mensagem}"
            
            Locais de atendimento disponíveis:
            {chr(10).join([f"- {local.nome} (cidade: {local.cidade})" for local in locais])}
            
            Analise a mensagem do usuário e identifique qual local ele deseja:
            
            Considere:
            - Nomes de cidades (Contagem, Belo Horizonte, BH)
            - Nomes dos locais
            - Variações e apelidos (Contagem = CTG, Belo Horizonte = BH)
            - Proximidade ou preferência mencionada
            
            Se o usuário mencionou um local válido, responda apenas com o nome EXATO do local da lista.
            Se não conseguir identificar ou se a mensagem for ambígua, responda "não encontrado".
            
            Exemplos:
            "quero em contagem" → Contagem
            "prefiro bh" → Belo Horizonte  
            "o mais próximo" → não encontrado (precisa ser mais específico)
            
            Resposta:
            """

            response = model.generate_content(prompt)

            local_nome = response.text.strip()
            local_escolhido = None

            # Buscar local exato
            for local in locais:
                if local.nome.lower() == local_nome.lower():
                    local_escolhido = local
                    break

            if not local_escolhido:
                logging.info(
                    f"IA não conseguiu identificar local para: '{mensagem}'. Resposta IA: '{local_nome}'"
                )
                return {
                    'success': False,
                    'message':
                    "Não consegui identificar o local desejado. Por favor, escolha uma das opções disponíveis:",
                    'tipo': 'locais',
                    'proximo_estado': 'local'
                }

            # Verificar se há especialidades disponíveis neste local
            especialidades_disponiveis = self._obter_especialidades_por_local(
                local_escolhido.id)

            if not especialidades_disponiveis:
                return {
                    'success': False,
                    'message':
                    f"Desculpe, não há especialidades disponíveis no local {local_escolhido.nome} no momento. Escolha outro local:",
                    'tipo': 'locais',
                    'proximo_estado': 'local'
                }

            # Salvar local escolhido
            dados = conversa.get_dados()
            dados['local_id'] = local_escolhido.id
            dados['local_nome'] = local_escolhido.nome
            conversa.set_dados(dados)
            conversa.estado = 'especialidade'

            logging.info(
                f"IA selecionou local: {local_escolhido.nome} para mensagem: '{mensagem}'"
            )

            return {
                'success': True,
                'message':
                f"Perfeito! Atendimento em **{local_escolhido.nome}** selecionado ✅\n\nAgora me diga, qual especialidade você precisa? Pode falar naturalmente, como 'dor de cabeça' ou 'problema no coração'.",
                'tipo': 'especialidades',
                'especialidades': especialidades_disponiveis,
                'proximo_estado': 'especialidade'
            }

        except Exception as e:
            logging.warning(
                f"IA temporariamente indisponível para seleção de local: {e}. Usando fallback."
            )

            # FALLBACK: Busca por palavras-chave nos locais disponíveis
            mensagem_lower = mensagem.lower()
            for local in locais_disponiveis:
                nome_local = local['nome'].lower()
                cidade_local = local.get('cidade', '').lower()

                if nome_local in mensagem_lower or cidade_local in mensagem_lower:
                    # Buscar especialidades para este local
                    local_obj = Local.query.get(local['id'])
                    especialidades_disponiveis = self._obter_especialidades_por_local(
                        local['id'])

                    if especialidades_disponiveis:
                        # Salvar local nos dados da conversa
                        dados = conversa.get_dados()
                        dados['local_id'] = local['id']
                        dados['local_nome'] = local['nome']
                        conversa.set_dados(dados)
                        conversa.estado = 'especialidade'

                        return {
                            'success': True,
                            'message':
                            f"Local identificado: {local['nome']}. Agora escolha a especialidade:",
                            'tipo': 'especialidades',
                            'especialidades': especialidades_disponiveis,
                            'proximo_estado': 'especialidade'
                        }
                    else:
                        return {
                            'success': False,
                            'message':
                            f"Não há especialidades disponíveis em {local['nome']} no momento. Escolha outro local:",
                            'tipo': 'locais',
                            'locais': locais_disponiveis,
                            'proximo_estado': 'local'
                        }

            # Se não conseguir identificar, mostrar lista
            return {
                'success': True,
                'message':
                "Não consegui identificar o local. Escolha um dos disponíveis:",
                'tipo': 'locais',
                'locais': locais_disponiveis,
                'proximo_estado': 'local'
            }

    def _obter_especialidades_por_local(self, local_id):
        """Obtém especialidades disponíveis em um local específico"""
        from models import Especialidade, Medico, HorarioDisponivel
        from app import db

        # Buscar especialidades que têm horários disponíveis no local
        especialidades_com_horarios = db.session.query(Especialidade).join(
            Medico, Especialidade.id == Medico.especialidade_id).join(
                HorarioDisponivel,
                Medico.id == HorarioDisponivel.medico_id).filter(
                    HorarioDisponivel.local_id == local_id,
                    HorarioDisponivel.ativo == True,
                    Especialidade.ativo == True,
                    Medico.ativo == True).distinct().all()

        return [{
            'id': esp.id,
            'nome': esp.nome,
            'descricao': esp.descricao
        } for esp in especialidades_com_horarios]

    def _buscar_horarios_disponiveis_por_local_especialidade(
            self, local_id, especialidade_id):
        """Busca próximos horários disponíveis para uma especialidade em um local específico"""
        from models import Medico, HorarioDisponivel, Agendamento
        from datetime import timedelta

        hoje = date.today()
        data_limite = hoje + timedelta(days=30)  # Próximos 30 dias

        # Buscar médicos da especialidade
        medicos = Medico.query.filter_by(especialidade_id=especialidade_id,
                                         ativo=True).all()

        horarios_disponiveis = []

        for medico in medicos:
            # Buscar horários configurados no local específico
            horarios_config = HorarioDisponivel.query.filter_by(
                medico_id=medico.id,
                local_id=local_id,  # Filtrar por local
                ativo=True).all()

            # Gerar horários dos próximos dias
            data_atual = hoje
            while data_atual <= data_limite and len(horarios_disponiveis) < 10:
                dia_semana = data_atual.weekday()  # 0=segunda

                # Verificar se médico atende neste dia no local
                horario_config = None
                for hc in horarios_config:
                    if hc.dia_semana == dia_semana:
                        horario_config = hc
                        break

                if horario_config:
                    # Gerar slots de horário
                    hora_atual = datetime.combine(data_atual,
                                                  horario_config.hora_inicio)
                    hora_fim = datetime.combine(data_atual,
                                                horario_config.hora_fim)
                    duracao = timedelta(
                        minutes=horario_config.duracao_consulta)

                    while hora_atual + duracao <= hora_fim:
                        # Verificar se horário já está ocupado por agendamento normal
                        agendamento_existente = Agendamento.query.filter_by(
                            medico_id=medico.id,
                            data=data_atual,
                            hora=hora_atual.time(),
                            status='agendado').first()

                        # Verificar se horário está bloqueado por agendamento recorrente
                        from models import AgendamentoRecorrente
                        dia_semana = data_atual.weekday()
                        agendamento_recorrente = AgendamentoRecorrente.query.filter(
                            AgendamentoRecorrente.medico_id == medico.id,
                            AgendamentoRecorrente.dia_semana == dia_semana,
                            AgendamentoRecorrente.hora == hora_atual.time(),
                            AgendamentoRecorrente.ativo == True,
                            AgendamentoRecorrente.data_inicio <= data_atual,
                            (AgendamentoRecorrente.data_fim.is_(None)) |
                            (AgendamentoRecorrente.data_fim
                             >= data_atual)).first()

                        # VERIFICAÇÃO ADICIONAL: Slots muito próximos no tempo (buffer de segurança)
                        agora = datetime.now()
                        horario_slot = datetime.combine(
                            data_atual, hora_atual.time())

                        # Não permitir agendamentos com menos de 2 horas de antecedência
                        if horario_slot <= agora + timedelta(hours=2):
                            # Pular este slot - muito próximo
                            pass
                        elif not agendamento_existente and not agendamento_recorrente:
                            horarios_disponiveis.append({
                                'medico_id':
                                medico.id,
                                'medico':
                                medico.nome,
                                'local_id':
                                horario_config.local_id,
                                'local':
                                horario_config.local_rel.nome
                                if horario_config.local_rel else 'N/A',
                                'data':
                                data_atual.strftime('%Y-%m-%d'),
                                'data_formatada':
                                data_atual.strftime('%d/%m/%Y') +
                                f' ({self._get_dia_semana(data_atual.weekday())})',
                                'hora':
                                hora_atual.strftime('%H:%M'),
                                'hora_formatada':
                                hora_atual.strftime('%H:%M'),
                                'dia_semana':
                                self._get_dia_semana(data_atual.weekday()),
                                'disponivel_desde':
                                agora.strftime(
                                    '%H:%M'
                                )  # Timestamp de quando ficou disponível
                            })

                        hora_atual += duracao

                data_atual += timedelta(days=1)

        return sorted(horarios_disponiveis,
                      key=lambda x: (x['data'], x['hora']))

    def _processar_especialidade(self, mensagem, conversa):
        """Processa seleção de especialidade"""
        from models import Especialidade, Medico, HorarioDisponivel

        dados = conversa.get_dados()
        local_id = dados.get('local_id')

        if not local_id:
            # Se não tem local, voltar para seleção de local
            conversa.estado = 'local'
            return {
                'success': False,
                'message':
                "É necessário selecionar um local primeiro. Escolha o local de atendimento:",
                'tipo': 'locais',
                'proximo_estado': 'local'
            }

        # Obter especialidades disponíveis no local selecionado
        especialidades_disponiveis = self._obter_especialidades_por_local(
            local_id)
        lista_especialidades = [
            esp['nome'] for esp in especialidades_disponiveis
        ]

        # Usar IA AVANÇADA para identificar especialidade baseada em sintomas e condições
        try:
            prompt = f"""
            Você é um médico especialista em triagem. O usuário está descrevendo sua necessidade médica.

            Mensagem do usuário: "{mensagem}"
            
            Especialidades disponíveis no local escolhido:
            {chr(10).join([f"- {esp['nome']}: {esp['descricao']}" for esp in especialidades_disponiveis])}
            
            ANALISE CUIDADOSAMENTE a mensagem e identifique qual especialidade é mais adequada considerando:
            
            SINTOMAS E CONDIÇÕES:
            - Dor de cabeça, enxaqueca, tontura → Clínica Geral ou Neurologia
            - Dor no peito, palpitação, pressão alta → Cardiologia
            - Problemas de pele, manchas, coceira → Dermatologia
            - Problemas nos olhos, visão → Oftalmologia
            - Problemas de criança, bebê → Pediatria
            - Problemas femininos, gravidez → Ginecologia
            - Dor nas costas, ossos, articulações → Ortopedia
            - Ansiedade, depressão, problemas mentais → Psiquiatria
            - Check-up, exames gerais → Clínica Geral
            
            ESPECIALIDADES MENCIONADAS DIRETAMENTE:
            - "cardiologista" → Cardiologia
            - "dermatologista" → Dermatologia
            - "ginecologista" → Ginecologia
            - etc.
            
            Se conseguir identificar uma especialidade adequada, responda apenas com o nome EXATO da especialidade da lista.
            Se não conseguir identificar ou for ambíguo, responda "não encontrado".
            
            Exemplos:
            "estou com dor de cabeça" → Clínica Geral
            "preciso de cardiologista" → Cardiologia
            "problema na pele" → Dermatologia
            "meu filho está doente" → Pediatria
            "quero fazer check-up" → Clínica Geral
            
            Resposta:
            """

            response = model.generate_content(prompt)

            especialidade_nome = response.text.strip()
            especialidade_escolhida = None

            # Buscar especialidade na lista filtrada por local
            for esp in especialidades_disponiveis:
                if esp['nome'].lower() == especialidade_nome.lower():
                    especialidade_escolhida = esp
                    break

            logging.info(
                f"IA identificou especialidade '{especialidade_nome}' para mensagem: '{mensagem}'"
            )

        except Exception as e:
            logging.warning(
                f"IA temporariamente indisponível para especialidade: {e}. Usando fallback."
            )

            # FALLBACK: Busca por palavras-chave simples
            mensagem_lower = mensagem.lower()

            # Mapeamento de sintomas/termos para especialidades
            mapeamento_especialidades = {
                'cardiologia':
                ['coração', 'pressão', 'peito', 'palpitação', 'cardio'],
                'dermatologia':
                ['pele', 'mancha', 'coceira', 'derma', 'espinha'],
                'pediatria': ['criança', 'bebê', 'pediatra', 'infant'],
                'ginecologia': ['gineco', 'mulher', 'menstruação', 'gravidez'],
                'ortopedia':
                ['osso', 'articulação', 'ortope', 'fratura', 'dor nas costas'],
                'oftalmologia': ['olho', 'visão', 'vista', 'oftamo'],
                'psiquiatria': ['depressão', 'ansiedade', 'mental', 'psiqui'],
                'clínica geral': ['geral', 'checkup', 'exame', 'rotina']
            }

            for esp_nome, palavras_chave in mapeamento_especialidades.items():
                if any(palavra in mensagem_lower
                       for palavra in palavras_chave):
                    # Procurar a especialidade na lista
                    for especialidade in especialidades_disponiveis:
                        if esp_nome.lower() in especialidade['nome'].lower():
                            return self._processar_especialidade_selecionada(
                                especialidade, conversa, dados)

            # Se não conseguir identificar, mostrar lista
            return {
                'success': True,
                'message':
                "Não consegui identificar a especialidade. Escolha uma das disponíveis:",
                'tipo': 'especialidades',
                'especialidades': especialidades_disponiveis,
                'proximo_estado': 'especialidade'
            }

        if not especialidade_escolhida:
            return {
                'success': False,
                'message':
                "Especialidade não encontrada. Escolha uma das opções disponíveis:",
                'tipo': 'especialidades',
                'especialidades': especialidades_disponiveis,
                'proximo_estado': 'especialidade'
            }

        # Buscar horários disponíveis no local e especialidade selecionados
        horarios_disponiveis = self._buscar_horarios_disponiveis_por_local_especialidade(
            local_id, especialidade_escolhida['id'])

        if not horarios_disponiveis:
            return {
                'success': False,
                'message':
                f"Desculpe, não há horários disponíveis para {especialidade_escolhida['nome']} no local {dados.get('local_nome', 'selecionado')} no momento. Escolha outra especialidade:",
                'tipo': 'especialidades',
                'especialidades': especialidades_disponiveis,
                'proximo_estado': 'especialidade'
            }

        # Salvar especialidade escolhida
        dados['especialidade_id'] = especialidade_escolhida['id']
        dados['especialidade_nome'] = especialidade_escolhida['nome']
        conversa.set_dados(dados)
        conversa.estado = 'horarios'

        return {
            'success': True,
            'message':
            f"Ótima escolha! {especialidade_escolhida['nome']} no {dados.get('local_nome', 'local selecionado')} ✅\n\nAqui estão os próximos horários disponíveis:",
            'tipo': 'horarios',
            'horarios': horarios_disponiveis[:5],  # Primeiros 5
            'proximo_estado': 'horarios'
        }

    def _processar_horarios(self, mensagem, conversa, dados):
        """Processa seleção de horário"""
        # Usar IA para identificar qual horário o usuário escolheu
        # CORREÇÃO: Usar a função que filtra por local E especialidade
        local_id = dados.get('local_id')
        horarios_disponiveis = self._buscar_horarios_disponiveis_por_local_especialidade(
            local_id, dados['especialidade_id'])

        prompt = f"""
        O usuário disse: "{mensagem}"
        
        Horários disponíveis:
        {self._formatar_horarios_para_ia(horarios_disponiveis[:5])}
        
        Qual horário o usuário escolheu? Responda apenas com o número da opção (1-5) ou "não encontrado".
        """

        try:
            response = model.generate_content(prompt)

            opcao = response.text.strip()

            try:
                indice = int(opcao) - 1
                if 0 <= indice < len(horarios_disponiveis):
                    horario_escolhido = horarios_disponiveis[indice]

                    # Salvar escolha
                    dados['horario_escolhido'] = horario_escolhido
                    conversa.set_dados(dados)
                    conversa.estado = 'confirmacao'

                    return {
                        'success': True,
                        'message':
                        f"Perfeito! Você escolheu:\n\n📅 {horario_escolhido['data_formatada']}\n🕐 {horario_escolhido['hora_formatada']}\n👨‍⚕️ Dr(a). {horario_escolhido['medico']}\n🏥 {dados['especialidade_nome']}\n📍 {horario_escolhido['local']}\n\nConfirma o agendamento? (Digite 'sim' para confirmar ou 'não' para escolher outro horário)",
                        'tipo': 'confirmacao',
                        'proximo_estado': 'confirmacao'
                    }
                else:
                    raise ValueError("Índice inválido")

            except (ValueError, IndexError):
                return {
                    'success': False,
                    'message':
                    "Opção inválida. Escolha um dos horários disponíveis digitando o número (1-5):",
                    'tipo': 'horarios',
                    'horarios': horarios_disponiveis[:5],
                    'proximo_estado': 'horarios'
                }

        except Exception as e:
            logging.error(f"Erro ao processar horário: {e}")
            return {
                'success': False,
                'message': "Erro ao processar horário. Escolha uma opção:",
                'tipo': 'horarios',
                'horarios': horarios_disponiveis[:5],
                'proximo_estado': 'horarios'
            }

    def _processar_confirmacao(self, mensagem, conversa, dados):
        """Processa confirmação do agendamento"""
        resposta = mensagem.strip().lower()

        if resposta in ['sim', 's', 'confirmar', 'confirmo', 'ok', 'yes']:
            # Validações antes de criar agendamento
            from models import Agendamento, Medico, Configuracao, AgendamentoRecorrente
            from app import db

            horario = dados['horario_escolhido']
            paciente_id = dados['paciente_id']
            especialidade_id = dados['especialidade_id']
            medico_id = horario['medico_id']
            data_agendamento = datetime.strptime(horario['data'],
                                                 '%Y-%m-%d').date()
            hora_agendamento = datetime.strptime(horario['hora'],
                                                 '%H:%M').time()

            # VALIDAÇÃO 1: Especialidades duplicadas
            bloquear_duplicadas = Configuracao.get_valor(
                'bloquear_especialidades_duplicadas', 'false')
            if bloquear_duplicadas == 'true':
                agendamento_existente = Agendamento.query.filter(
                    Agendamento.paciente_id == paciente_id,
                    Agendamento.especialidade_id == especialidade_id,
                    Agendamento.status == 'agendado', Agendamento.data
                    >= date.today()).first()

                if agendamento_existente:
                    from models import Paciente, Especialidade
                    paciente = Paciente.query.get(paciente_id)
                    especialidade = Especialidade.query.get(especialidade_id)
                    return {
                        'success': False,
                        'message':
                        f"❌ {paciente.nome}, você já possui um agendamento ativo na especialidade {especialidade.nome}.\n\n📋 Por política da clínica, não é permitido ter consultas agendadas com médicos diferentes da mesma especialidade.\n\nPara reagendar ou cancelar sua consulta existente, digite 'cancelar'.",
                        'tipo': 'erro',
                        'proximo_estado': 'inicio'
                    }

            # Buscar informações do médico para validar agenda recorrente
            medico = Medico.query.get(medico_id)

            # VALIDAÇÃO CRÍTICA: Verificar se horário ainda está disponível (prevenção de race condition)
            agendamento_conflito = Agendamento.query.filter_by(
                medico_id=medico_id,
                data=data_agendamento,
                hora=hora_agendamento,
                status='agendado').first()

            if agendamento_conflito:
                return {
                    'success':
                    False,
                    'message':
                    f"❌ Este horário acabou de ser ocupado por outro paciente!\n\n⏰ Horário: {horario['hora_formatada']} de {data_agendamento.strftime('%d/%m/%Y')}\n👨‍⚕️ Médico: Dr(a). {horario['medico']}\n\n🔄 Por favor, escolha outro horário disponível:",
                    'tipo':
                    'horarios_atualizados',
                    'horarios':
                    self._buscar_horarios_disponiveis_por_local_especialidade(
                        horario['local_id'], especialidade_id)[:5],
                    'proximo_estado':
                    'horarios'
                }

            # Verificar agendamentos recorrentes que possam conflitar
            from models import AgendamentoRecorrente
            dia_semana_agendamento = data_agendamento.weekday()
            recorrente_conflito = AgendamentoRecorrente.query.filter(
                AgendamentoRecorrente.medico_id == medico_id,
                AgendamentoRecorrente.dia_semana == dia_semana_agendamento,
                AgendamentoRecorrente.hora == hora_agendamento,
                AgendamentoRecorrente.ativo == True,
                AgendamentoRecorrente.data_inicio <= data_agendamento,
                (AgendamentoRecorrente.data_fim.is_(None)) |
                (AgendamentoRecorrente.data_fim >= data_agendamento)).first()

            if recorrente_conflito:
                return {
                    'success':
                    False,
                    'message':
                    f"❌ Este horário está bloqueado por agendamento recorrente!\n\n⏰ Horário: {horario['hora_formatada']} de {data_agendamento.strftime('%d/%m/%Y')}\n👨‍⚕️ Médico: Dr(a). {horario['medico']}\n\n🔄 Por favor, escolha outro horário disponível:",
                    'tipo':
                    'horarios_atualizados',
                    'horarios':
                    self._buscar_horarios_disponiveis_por_local_especialidade(
                        horario['local_id'], especialidade_id)[:5],
                    'proximo_estado':
                    'horarios'
                }

            # Criar agendamento principal (agora com segurança)
            novo_agendamento = Agendamento(paciente_id=paciente_id,
                                           medico_id=medico_id,
                                           especialidade_id=especialidade_id,
                                           local_id=horario['local_id'],
                                           data=data_agendamento,
                                           hora=hora_agendamento,
                                           status='agendado')

            db.session.add(novo_agendamento)
            db.session.flush()  # Para obter o ID do agendamento

            # VALIDAÇÃO 2: Agendamentos recorrentes
            if medico and medico.agenda_recorrente:
                duracao_semanas = int(
                    Configuracao.get_valor('duracao_agendamento_recorrente',
                                           '4'))
                dia_semana = data_agendamento.weekday()  # 0=segunda, 6=domingo
                data_fim = data_agendamento + timedelta(weeks=duracao_semanas)

                # Criar agendamento recorrente
                agendamento_recorrente = AgendamentoRecorrente(
                    paciente_id=paciente_id,
                    medico_id=medico_id,
                    especialidade_id=especialidade_id,
                    local_id=horario['local_id'],
                    dia_semana=dia_semana,
                    hora=hora_agendamento,
                    data_inicio=data_agendamento,
                    data_fim=data_fim,
                    ativo=True,
                    observacoes=
                    f'Gerado automaticamente a partir do agendamento #{novo_agendamento.id}'
                )

                db.session.add(agendamento_recorrente)

            db.session.commit()

            # Finalizar conversa
            conversa.estado = 'finalizado'

            # Formatear data com dia da semana em português
            data_obj = datetime.strptime(horario['data'], '%Y-%m-%d')
            data_formatada_completa = data_obj.strftime(
                '%d/%m/%Y') + f' ({self._get_dia_semana(data_obj.weekday())})'

            # Buscar informações do paciente para mostrar tipo de atendimento e idade
            from models import Paciente
            paciente = Paciente.query.get(dados['paciente_id'])
            tipo_atendimento_msg = ""
            idade_msg = ""
            if paciente:
                # Tipo de atendimento
                if paciente.tipo_atendimento == 'plano':
                    tipo_atendimento_msg = f"\n💳 Tipo: Plano de Saúde (Carteirinha: {paciente.carteirinha})"
                else:
                    tipo_atendimento_msg = "\n💰 Tipo: Atendimento Particular"

                # Calcular idade se tiver data de nascimento
                if paciente.data_nascimento:
                    from datetime import date
                    hoje = date.today()
                    idade = hoje.year - paciente.data_nascimento.year - (
                        (hoje.month, hoje.day)
                        < (paciente.data_nascimento.month,
                           paciente.data_nascimento.day))
                    idade_msg = f"\n👤 Idade: {idade} anos"

            # Buscar informações completas do local selecionado
            from models import Local
            local_selecionado = Local.query.get(horario['local_id'])
            endereco_completo = ""
            telefone_local = ""

            if local_selecionado:
                if local_selecionado.endereco:
                    endereco_completo = f"\n🏠 Endereço: {local_selecionado.endereco}, {local_selecionado.cidade}"
                else:
                    endereco_completo = f"\n🏠 Cidade: {local_selecionado.cidade}"

                if local_selecionado.telefone:
                    telefone_local = f"\n☎️ Telefone do Local: {local_selecionado.telefone}"

            # Mensagem personalizada baseada no tipo de agenda
            mensagem_recorrencia = ""
            if medico and medico.agenda_recorrente:
                duracao_semanas = int(
                    Configuracao.get_valor('duracao_agendamento_recorrente',
                                           '4'))
                mensagem_recorrencia = f"\n\n🔄 AGENDA FIXA: Você ficará com este mesmo horário ({self._get_dia_semana(data_agendamento.weekday())} às {horario['hora_formatada']}) por {duracao_semanas} semanas."

            return {
                'success': True,
                'message':
                f"🎉 Agendamento confirmado com sucesso!\n\n📄 Número: #{novo_agendamento.id}\n📅 Data: {data_formatada_completa}\n🕐 Horário: {horario['hora_formatada']}\n👨‍⚕️ Médico: Dr(a). {horario['medico']}\n🏥 Especialidade: {dados['especialidade_nome']}\n📍 Local: {horario['local']}{endereco_completo}{telefone_local}{idade_msg}{tipo_atendimento_msg}{mensagem_recorrencia}\n\n📱 IMPORTANTE: Tire um print desta tela para guardar as informações do seu agendamento!\n\n✅ Lembre-se de chegar 15 minutos antes.\n\nDesenvolvido por João Layon | Para novo agendamento, digite 'oi'",
                'tipo': 'sucesso',
                'agendamento_id': novo_agendamento.id,
                'proximo_estado': 'finalizado'
            }

        elif resposta in ['não', 'nao', 'n', 'cancelar', 'não confirmo']:
            # Voltar para escolha de horários
            conversa.estado = 'horarios'
            local_id = dados.get('local_id')
            horarios_disponiveis = self._buscar_horarios_disponiveis_por_local_especialidade(
                local_id, dados['especialidade_id'])

            return {
                'success': True,
                'message': "Sem problemas! Escolha outro horário:",
                'tipo': 'horarios',
                'horarios': horarios_disponiveis[:5],
                'proximo_estado': 'horarios'
            }
        else:
            return {
                'success': False,
                'message':
                "Não entendi. Digite 'sim' para confirmar ou 'não' para escolher outro horário:",
                'tipo': 'confirmacao',
                'proximo_estado': 'confirmacao'
            }

    def _processar_cancelamento(self, mensagem, conversa):
        """Processa cancelamento de consulta"""
        # Se ainda não tem CPF, extrair CPF
        dados = conversa.get_dados()

        if 'cpf_cancelamento' not in dados:
            cpf = self._extrair_cpf(mensagem)
            if not cpf:
                return {
                    'success': False,
                    'message': "CPF inválido. Digite apenas os 11 números:",
                    'tipo': 'texto',
                    'proximo_estado': 'cancelamento'
                }

            # Buscar agendamentos do paciente
            from models import Paciente, Agendamento
            paciente = Paciente.query.filter_by(cpf=cpf).first()

            if not paciente:
                return {
                    'success': False,
                    'message':
                    "CPF não encontrado no sistema. Verifique e digite novamente:",
                    'tipo': 'texto',
                    'proximo_estado': 'cancelamento'
                }

            agendamentos = Agendamento.query.filter_by(
                paciente_id=paciente.id, status='agendado').filter(
                    Agendamento.data >= date.today()).all()

            if not agendamentos:
                conversa.estado = 'finalizado'
                return {
                    'success': True,
                    'message':
                    f"Olá, {paciente.nome}! Você não possui consultas agendadas para cancelar.\n\nPara novo agendamento, digite 'oi'",
                    'tipo': 'info',
                    'proximo_estado': 'finalizado'
                }

            dados['cpf_cancelamento'] = cpf
            dados['paciente_cancelamento'] = paciente.id
            dados['agendamentos_cancelamento'] = [ag.id for ag in agendamentos]
            conversa.set_dados(dados)

            return {
                'success': True,
                'message': f"Olá, {paciente.nome}! Suas consultas agendadas:",
                'tipo': 'agendamentos_cancelamento',
                'agendamentos': [ag.to_dict() for ag in agendamentos],
                'proximo_estado': 'cancelamento'
            }

        else:
            # Processar qual agendamento cancelar
            from models import Agendamento
            from app import db

            # Usar IA para identificar qual agendamento cancelar
            agendamentos_ids = dados['agendamentos_cancelamento']
            agendamentos = Agendamento.query.filter(
                Agendamento.id.in_(agendamentos_ids)).all()

            prompt = f"""
            O usuário disse: "{mensagem}"
            
            Agendamentos disponíveis para cancelamento:
            {self._formatar_agendamentos_para_ia(agendamentos)}
            
            Qual agendamento o usuário quer cancelar? Responda apenas com o número da opção ou "não encontrado".
            """

            try:
                response = model.generate_content(prompt)

                opcao = response.text.strip()

                try:
                    indice = int(opcao) - 1
                    if 0 <= indice < len(agendamentos):
                        agendamento = agendamentos[indice]

                        # Cancelar agendamento
                        agendamento.status = 'cancelado'
                        agendamento.cancelado_em = datetime.utcnow()
                        agendamento.motivo_cancelamento = 'Cancelado pelo paciente via chatbot'

                        db.session.commit()

                        conversa.estado = 'finalizado'

                        return {
                            'success': True,
                            'message':
                            f"✅ Consulta cancelada com sucesso!\n\n📄 Número: #{agendamento.id}\n📅 Data: {agendamento.data.strftime('%d/%m/%Y')}\n🕐 Horário: {agendamento.hora.strftime('%H:%M')}\n👨‍⚕️ Médico: Dr(a). {agendamento.medico_rel.nome}\n\n❌ Status: CANCELADA\n\nPara novo agendamento, digite 'oi'",
                            'tipo': 'sucesso',
                            'proximo_estado': 'finalizado'
                        }
                    else:
                        raise ValueError("Índice inválido")

                except (ValueError, IndexError):
                    return {
                        'success': False,
                        'message':
                        "Opção inválida. Digite o número da consulta que deseja cancelar:",
                        'tipo': 'agendamentos_cancelamento',
                        'agendamentos': [ag.to_dict() for ag in agendamentos],
                        'proximo_estado': 'cancelamento'
                    }

            except Exception as e:
                logging.error(f"Erro ao processar cancelamento: {e}")
                return {
                    'success': False,
                    'message':
                    "Erro ao processar cancelamento. Digite o número da consulta:",
                    'tipo': 'agendamentos_cancelamento',
                    'agendamentos': [ag.to_dict() for ag in agendamentos],
                    'proximo_estado': 'cancelamento'
                }

    def _buscar_horarios_disponiveis(self, especialidade_id):
        """Busca próximos horários disponíveis para uma especialidade"""
        from models import Medico, HorarioDisponivel, Agendamento
        from datetime import timedelta

        hoje = date.today()
        data_limite = hoje + timedelta(days=30)  # Próximos 30 dias

        # Buscar médicos da especialidade
        medicos = Medico.query.filter_by(especialidade_id=especialidade_id,
                                         ativo=True).all()

        horarios_disponiveis = []

        for medico in medicos:
            # Buscar horários configurados
            horarios_config = HorarioDisponivel.query.filter_by(
                medico_id=medico.id, ativo=True).all()

            # Gerar horários dos próximos dias
            data_atual = hoje
            while data_atual <= data_limite and len(horarios_disponiveis) < 10:
                dia_semana = data_atual.weekday()  # 0=segunda

                # Verificar se médico atende neste dia
                horario_config = None
                for hc in horarios_config:
                    if hc.dia_semana == dia_semana:
                        horario_config = hc
                        break

                if horario_config:
                    # Gerar slots de horário
                    hora_atual = datetime.combine(data_atual,
                                                  horario_config.hora_inicio)
                    hora_fim = datetime.combine(data_atual,
                                                horario_config.hora_fim)
                    duracao = timedelta(
                        minutes=horario_config.duracao_consulta)

                    while hora_atual + duracao <= hora_fim:
                        # Verificar se horário já está ocupado por agendamento normal
                        agendamento_existente = Agendamento.query.filter_by(
                            medico_id=medico.id,
                            data=data_atual,
                            hora=hora_atual.time(),
                            status='agendado').first()

                        # Verificar se horário está bloqueado por agendamento recorrente
                        from models import AgendamentoRecorrente
                        dia_semana = data_atual.weekday()
                        agendamento_recorrente = AgendamentoRecorrente.query.filter(
                            AgendamentoRecorrente.medico_id == medico.id,
                            AgendamentoRecorrente.dia_semana == dia_semana,
                            AgendamentoRecorrente.hora == hora_atual.time(),
                            AgendamentoRecorrente.ativo == True,
                            AgendamentoRecorrente.data_inicio <= data_atual,
                            (AgendamentoRecorrente.data_fim.is_(None)) |
                            (AgendamentoRecorrente.data_fim
                             >= data_atual)).first()

                        # VERIFICAÇÃO ADICIONAL: Slots muito próximos no tempo (buffer de segurança)
                        agora = datetime.now()
                        horario_slot = datetime.combine(
                            data_atual, hora_atual.time())

                        # Não permitir agendamentos com menos de 2 horas de antecedência
                        if horario_slot <= agora + timedelta(hours=2):
                            # Pular este slot - muito próximo
                            pass
                        elif not agendamento_existente and not agendamento_recorrente:
                            horarios_disponiveis.append({
                                'medico_id':
                                medico.id,
                                'medico':
                                medico.nome,
                                'local_id':
                                horario_config.local_id,
                                'local':
                                horario_config.local_rel.nome
                                if horario_config.local_rel else 'N/A',
                                'data':
                                data_atual.strftime('%Y-%m-%d'),
                                'data_formatada':
                                data_atual.strftime('%d/%m/%Y') +
                                f' ({self._get_dia_semana(data_atual.weekday())})',
                                'hora':
                                hora_atual.strftime('%H:%M'),
                                'hora_formatada':
                                hora_atual.strftime('%H:%M'),
                                'dia_semana':
                                self._get_dia_semana(data_atual.weekday()),
                                'disponivel_desde':
                                agora.strftime(
                                    '%H:%M'
                                )  # Timestamp de quando ficou disponível
                            })

                        hora_atual += duracao

                data_atual += timedelta(days=1)

        return sorted(horarios_disponiveis,
                      key=lambda x: (x['data'], x['hora']))

    def _extrair_cpf(self, texto):
        """Extrai CPF do texto"""
        import re
        # Remove tudo que não é número
        numeros = re.sub(r'[^\d]', '', texto)
        if len(numeros) == 11:
            return numeros
        return None

    def _extrair_telefone(self, texto):
        """Extrai telefone do texto"""
        import re
        numeros = re.sub(r'[^\d]', '', texto)
        if len(numeros) >= 10 and len(numeros) <= 11:
            return numeros
        return None

    def _extrair_email(self, texto):
        """Extrai email do texto"""
        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(email_pattern, texto)
        return match.group() if match else None

    def _formatar_cpf(self, cpf):
        """Formata CPF para exibição"""
        return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"

    def _formatar_horarios_para_ia(self, horarios):
        """Formata horários para prompt da IA"""
        texto = ""
        for i, h in enumerate(horarios, 1):
            texto += f"{i}. {h['data_formatada']} ({h['dia_semana']}) às {h['hora_formatada']} - Dr(a). {h['medico']}\n"
        return texto

    def _formatar_agendamentos_para_ia(self, agendamentos):
        """Formata agendamentos para prompt da IA"""
        texto = ""
        for i, ag in enumerate(agendamentos, 1):
            texto += f"{i}. {ag.data.strftime('%d/%m/%Y')} às {ag.hora.strftime('%H:%M')} - Dr(a). {ag.medico_rel.nome} ({ag.especialidade_rel.nome})\n"
        return texto

    def _eh_saudacao(self, mensagem):
        """Detecta se a mensagem é uma saudação para resetar conversa"""
        mensagem_lower = mensagem.lower().strip()

        # Saudações comuns que devem sempre resetar a conversa
        saudacoes = [
            'oi', 'ola', 'olá', 'ola!', 'oi!', 'olá!', 'bom dia', 'boa tarde',
            'boa noite', 'hello', 'hi', 'hey', 'e aí', 'eai', 'ola pessoal',
            'oi pessoal', 'tudo bem', 'como vai', 'opa', 'começar', 'iniciar',
            'começar de novo', 'reiniciar', 'recomeçar', 'novo agendamento'
        ]

        # Verificar se é uma saudação exata ou no início da mensagem
        for saudacao in saudacoes:
            if mensagem_lower == saudacao or mensagem_lower.startswith(
                    saudacao + ' '):
                return True

        # Usar IA para detectar saudações mais complexas
        try:
            prompt = f"""
            Analise se esta mensagem é uma saudação ou cumprimento que indica que o usuário quer COMEÇAR uma nova conversa:
            
            Mensagem: "{mensagem}"
            
            Responda APENAS "sim" se for uma saudação/cumprimento que indica início de conversa.
            Responda APENAS "não" se não for uma saudação ou se for parte de uma conversa já em andamento.
            
            Exemplos de SIM: "oi", "olá", "bom dia", "oi tudo bem", "olá, preciso agendar"
            Exemplos de NÃO: "5", "sim", "cardiologia", "12345678901", "não"
            """

            response = model.generate_content(prompt)

            resultado = response.text.strip().lower(
            ) if response.text else "não"
            return resultado == "sim"

        except Exception:
            # Se IA falhar, usar detecção básica
            return False

    def _eh_cancelamento(self, mensagem):
        """Verifica se a mensagem indica intenção de cancelamento"""
        palavras_cancelamento = [
            'cancelar', 'desmarcar', 'remover consulta', 'cancelo',
            'cancelamento', 'cancelar consulta'
        ]
        mensagem_lower = mensagem.lower().strip()
        return any(palavra in mensagem_lower
                   for palavra in palavras_cancelamento)

    def _validar_data_nascimento(self, data_str):
        """Valida e converte data de nascimento"""
        import re
        from datetime import datetime, date

        try:
            # Log para debug
            logging.info(f"Validando data: '{data_str}'")

            # Remover espaços e caracteres especiais exceto /
            data_limpa = re.sub(r'[^\d/]', '', data_str.strip())
            logging.info(f"Data limpa: '{data_limpa}'")

            # Tentar diferentes formatos
            formatos = ['%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y']

            for formato in formatos:
                try:
                    data_obj = datetime.strptime(data_limpa, formato)
                    data_nascimento = data_obj.date()
                    logging.info(
                        f"Data parseada com formato {formato}: {data_nascimento}"
                    )

                    # Validações básicas
                    hoje = date.today()
                    idade_maxima = hoje.replace(year=hoje.year -
                                                120)  # 120 anos max

                    if data_nascimento > hoje:
                        logging.info(
                            f"Data rejeitada - no futuro: {data_nascimento} > {hoje}"
                        )
                        return None  # Data no futuro

                    if data_nascimento < idade_maxima:
                        logging.info(
                            f"Data rejeitada - muito antiga: {data_nascimento} < {idade_maxima}"
                        )
                        return None  # Muito antiga

                    logging.info(f"Data válida aceita: {data_nascimento}")
                    return data_nascimento

                except ValueError as e:
                    logging.info(f"Formato {formato} falhou: {e}")
                    continue

            logging.info("Nenhum formato de data funcionou")
            return None

        except Exception as e:
            logging.error(f"Erro na validação da data: {e}")
            return None

    def _get_dia_semana(self, numero):
        """Retorna nome do dia da semana"""
        dias = [
            'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado',
            'Domingo'
        ]
        return dias[numero]

    def _processar_cancelamento_cpf_valido(self, conversa, paciente):
        """Processa cancelamento quando CPF é válido"""
        from models import Agendamento
        from datetime import date

        agendamentos = Agendamento.query.filter_by(
            paciente_id=paciente.id,
            status='agendado').filter(Agendamento.data >= date.today()).all()

        if not agendamentos:
            conversa.estado = 'finalizado'
            return {
                'success': True,
                'message':
                f"Olá, {paciente.nome}! Você não possui consultas agendadas para cancelar.\n\nPara novo agendamento, digite 'oi'",
                'tipo': 'info',
                'proximo_estado': 'finalizado'
            }

        dados = conversa.get_dados() or {}
        dados['cpf_cancelamento'] = paciente.cpf
        dados['paciente_cancelamento'] = paciente.id
        dados['agendamentos_cancelamento'] = [ag.id for ag in agendamentos]
        conversa.set_dados(dados)
        conversa.estado = 'cancelamento'

        return {
            'success': True,
            'message': f"Olá, {paciente.nome}! Suas consultas agendadas:",
            'tipo': 'agendamentos_cancelamento',
            'agendamentos': [ag.to_dict() for ag in agendamentos],
            'proximo_estado': 'cancelamento'
        }

    def _processar_consulta_agendamentos_cpf_valido(self, conversa, paciente):
        """Processa consulta de agendamentos quando CPF é válido"""
        from models import Agendamento
        from datetime import date

        # Buscar todos os agendamentos do paciente (passados e futuros)
        agendamentos_futuros = Agendamento.query.filter_by(
            paciente_id=paciente.id, status='agendado').filter(
                Agendamento.data >= date.today()).order_by(
                    Agendamento.data, Agendamento.hora).all()

        agendamentos_passados = Agendamento.query.filter_by(
            paciente_id=paciente.id).filter(
                Agendamento.data < date.today()).order_by(
                    Agendamento.data.desc(),
                    Agendamento.hora.desc()).limit(3).all()

        conversa.estado = 'finalizado'

        mensagem = f"📋 **Seus Agendamentos - {paciente.nome}**\n\n"

        if agendamentos_futuros:
            mensagem += "**🗓️ Próximas Consultas:**\n"
            for ag in agendamentos_futuros:
                status_emoji = "✅" if ag.status == 'agendado' else "❌"
                medico_nome = ag.medico_rel.nome if hasattr(
                    ag, 'medico_rel') and ag.medico_rel else 'N/A'
                especialidade_nome = ag.especialidade_rel.nome if hasattr(
                    ag,
                    'especialidade_rel') and ag.especialidade_rel else 'N/A'
                mensagem += f"{status_emoji} {ag.data.strftime('%d/%m/%Y')} às {ag.hora.strftime('%H:%M')}\n"
                mensagem += f"   👨‍⚕️ Dr(a). {medico_nome}\n"
                mensagem += f"   🏥 {especialidade_nome}\n\n"
        else:
            mensagem += "**🗓️ Próximas Consultas:**\nNenhuma consulta agendada.\n\n"

        if agendamentos_passados:
            mensagem += "**📚 Últimas Consultas:**\n"
            for ag in agendamentos_passados:
                status_emoji = "✅" if ag.status == 'concluido' else "❌" if ag.status == 'cancelado' else "⏳"
                mensagem += f"{status_emoji} {ag.data.strftime('%d/%m/%Y')} - {ag.status.title()}\n"

        mensagem += "\n💡 **Precisa de algo mais?**\n"
        mensagem += "• Digite 'agendar' para nova consulta\n"
        mensagem += "• Digite 'cancelar' para cancelar consulta\n"
        mensagem += "• Digite 'oi' para voltar ao menu"

        return {
            'success': True,
            'message': mensagem,
            'tipo': 'consulta_resultado',
            'proximo_estado': 'finalizado'
        }

    def _processar_consulta_agendamentos(self, mensagem, conversa):
        """Processa consulta de agendamentos (mesmo fluxo que cancelamento de CPF)"""
        return self._processar_cpf(mensagem, conversa)

    def _resposta_erro(self, mensagem):
        """Retorna resposta de erro padrão"""
        return {
            'success': False,
            'message': mensagem,
            'tipo': 'erro',
            'proximo_estado': 'inicio'
        }


# Instância global do serviço
chatbot_service = ChatbotService()
