import json
import os
import logging
from datetime import datetime, date, time, timedelta
import google.generativeai as genai

# Importar novos modelos SQLite
from models_sqlite import (
    Paciente, Local, Especialidade, Medico, HorarioDisponivel, 
    Agendamento, Conversa, Configuracao, AgendamentoRecorrente
)

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
            nome_clinica = Configuracao.get_valor('nome_clinica', 'Clínica João Layon')
            telefone = Configuracao.get_valor('telefone_clinica', '(31) 3333-4444')
            horario = Configuracao.get_valor('horario_funcionamento', 'Segunda a Sexta, 8h às 18h')

            # Buscar locais ativos
            locais = Local.find_active()
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
            nome_clinica = Configuracao.get_valor('nome_clinica', 'Clínica João Layon')
            nome_assistente = Configuracao.get_valor('nome_assistente', 'Assistente Virtual')
            telefone = Configuracao.get_valor('telefone_clinica', '(31) 3333-4444')

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
        paciente = Paciente.find_by_cpf(cpf)

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
            novo_paciente = Paciente.create(
                cpf=dados['cpf'],
                nome=dados['nome'],
                data_nascimento=dados.get('data_nascimento'),
                telefone=dados['telefone'],
                email=dados.get('email'),
                carteirinha=dados.get('carteirinha'),
                tipo_atendimento=dados.get('tipo_atendimento', 'particular'))

            # Salvar novo paciente com transação segura
            try:
                conversa.paciente_id = novo_paciente.id
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
            except Exception as e:
                logging.error(f"Erro ao salvar paciente: {e}")
                return {
                    'success': False,
                    'message':
                    'Erro interno ao cadastrar paciente. Tente novamente.',
                    'tipo': 'erro',
                    'proximo_estado': 'inicio'
                }

    def _processar_local(self, mensagem, conversa):
        """Processa seleção de local de atendimento usando IA AVANÇADA"""
        # Buscar locais ativos
        locais = Local.find_active()
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
            
            Analise a mensagem e identifique qual local o usuário quer escolher.
            Se não conseguir identificar um local específico, responda "indefinido".
            
            Responda APENAS com o nome EXATO do local escolhido ou "indefinido".
            """

            response = model.generate_content(prompt)
            escolha_ia = response.text.strip() if response.text else ""

            # Tentar encontrar o local escolhido
            local_escolhido = None
            for local in locais:
                if local.nome.lower() in escolha_ia.lower() or escolha_ia.lower() in local.nome.lower():
                    local_escolhido = local
                    break

            # Se IA não funcionou, tentar detecção manual
            if not local_escolhido:
                mensagem_lower = mensagem.lower().strip()
                for local in locais:
                    if (local.nome.lower() in mensagem_lower or 
                        (local.cidade and local.cidade.lower() in mensagem_lower)):
                        local_escolhido = local
                        break

            if local_escolhido:
                # Salvar local escolhido
                dados = conversa.get_dados() or {}
                dados['local_id'] = local_escolhido.id
                dados['local_nome'] = local_escolhido.nome
                conversa.set_dados(dados)
                conversa.estado = 'especialidade'

                return {
                    'success': True,
                    'message':
                    f"Perfeito! Local escolhido: **{local_escolhido.nome}** 📍\n\nAgora, qual especialidade médica você precisa?",
                    'tipo': 'especialidades',
                    'proximo_estado': 'especialidade'
                }
            else:
                # Não conseguiu identificar - mostrar opções
                locais_lista = "\n".join([
                    f"• **{local.nome}** - {local.cidade}"
                    for local in locais
                ])
                
                return {
                    'success': False,
                    'message':
                    f"Não consegui identificar o local. Por favor, escolha um dos locais disponíveis:\n\n{locais_lista}\n\nDigite o nome do local desejado:",
                    'tipo': 'locais',
                    'proximo_estado': 'local'
                }

        except Exception as e:
            logging.warning(f"Erro na IA para seleção de local: {e}")
            
            # Fallback manual
            mensagem_lower = mensagem.lower().strip()
            for local in locais:
                if (local.nome.lower() in mensagem_lower or 
                    (local.cidade and local.cidade.lower() in mensagem_lower)):
                    dados = conversa.get_dados() or {}
                    dados['local_id'] = local.id
                    dados['local_nome'] = local.nome
                    conversa.set_dados(dados)
                    conversa.estado = 'especialidade'

                    return {
                        'success': True,
                        'message':
                        f"Perfeito! Local escolhido: **{local.nome}** 📍\n\nAgora, qual especialidade médica você precisa?",
                        'tipo': 'especialidades',
                        'proximo_estado': 'especialidade'
                    }
            
            # Não conseguiu identificar - mostrar opções
            locais_lista = "\n".join([
                f"• **{local.nome}** - {local.cidade}"
                for local in locais
            ])
            
            return {
                'success': False,
                'message':
                f"Não consegui identificar o local. Por favor, escolha um dos locais disponíveis:\n\n{locais_lista}\n\nDigite o nome do local desejado:",
                'tipo': 'locais',
                'proximo_estado': 'local'
            }

    def _processar_especialidade(self, mensagem, conversa):
        """Processa seleção de especialidade usando IA AVANÇADA"""
        # Buscar especialidades ativas
        especialidades = Especialidade.find_active()
        especialidades_info = [f"{esp.nome} - {esp.descricao or 'Sem descrição'}" for esp in especialidades]

        try:
            prompt = f"""
            Você é um assistente médico especializado. O usuário está escolhendo uma especialidade médica.

            Mensagem do usuário: "{mensagem}"
            
            Especialidades médicas disponíveis:
            {chr(10).join([f"- {esp.nome}: {esp.descricao or 'Especialidade médica'}" for esp in especialidades])}
            
            Analise a mensagem do usuário e identifique qual especialidade médica ele precisa.
            Considere:
            - Sintomas mencionados
            - Tipo de problema de saúde
            - Menção direta da especialidade
            - Contexto médico
            
            Se não conseguir identificar uma especialidade específica, responda "indefinido".
            
            Responda APENAS com o nome EXATO da especialidade escolhida ou "indefinido".
            """

            response = model.generate_content(prompt)
            escolha_ia = response.text.strip() if response.text else ""

            # Tentar encontrar a especialidade escolhida
            especialidade_escolhida = None
            for esp in especialidades:
                if esp.nome.lower() in escolha_ia.lower() or escolha_ia.lower() in esp.nome.lower():
                    especialidade_escolhida = esp
                    break

            # Se IA não funcionou, tentar detecção manual
            if not especialidade_escolhida:
                mensagem_lower = mensagem.lower().strip()
                for esp in especialidades:
                    if esp.nome.lower() in mensagem_lower:
                        especialidade_escolhida = esp
                        break

                # Busca por palavras-chave relacionadas
                if not especialidade_escolhida:
                    mapeamento_sintomas = {
                        'coração': 'Cardiologia',
                        'pele': 'Dermatologia',
                        'criança': 'Pediatria',
                        'mulher': 'Ginecologia',
                        'osso': 'Ortopedia',
                        'mental': 'Psiquiatria',
                        'olho': 'Oftalmologia'
                    }
                    
                    for palavra, especialidade_nome in mapeamento_sintomas.items():
                        if palavra in mensagem_lower:
                            for esp in especialidades:
                                if esp.nome == especialidade_nome:
                                    especialidade_escolhida = esp
                                    break
                            if especialidade_escolhida:
                                break

            if especialidade_escolhida:
                # Salvar especialidade escolhida
                dados = conversa.get_dados() or {}
                dados['especialidade_id'] = especialidade_escolhida.id
                dados['especialidade_nome'] = especialidade_escolhida.nome
                conversa.set_dados(dados)
                conversa.estado = 'horarios'

                # Buscar médicos da especialidade no local escolhido
                medicos_especialidade = [m for m in Medico.find_active() 
                                       if m.especialidade_id == especialidade_escolhida.id]
                
                if not medicos_especialidade:
                    return {
                        'success': False,
                        'message':
                        f"Desculpe, não temos médicos de {especialidade_escolhida.nome} disponíveis no momento. Por favor, escolha outra especialidade:",
                        'tipo': 'especialidades',
                        'proximo_estado': 'especialidade'
                    }

                return {
                    'success': True,
                    'message':
                    f"Especialidade escolhida: **{especialidade_escolhida.nome}** 🩺\n\nVou buscar os horários disponíveis...",
                    'tipo': 'horarios',
                    'proximo_estado': 'horarios'
                }
            else:
                # Não conseguiu identificar - mostrar opções
                especialidades_lista = "\n".join([
                    f"• **{esp.nome}** - {esp.descricao or 'Especialidade médica'}"
                    for esp in especialidades
                ])
                
                return {
                    'success': False,
                    'message':
                    f"Não consegui identificar a especialidade. Por favor, escolha uma das especialidades disponíveis:\n\n{especialidades_lista}\n\nDigite o nome da especialidade desejada:",
                    'tipo': 'especialidades',
                    'proximo_estado': 'especialidade'
                }

        except Exception as e:
            logging.warning(f"Erro na IA para seleção de especialidade: {e}")
            
            # Fallback manual similar ao implementado acima
            mensagem_lower = mensagem.lower().strip()
            for esp in especialidades:
                if esp.nome.lower() in mensagem_lower:
                    dados = conversa.get_dados() or {}
                    dados['especialidade_id'] = esp.id
                    dados['especialidade_nome'] = esp.nome
                    conversa.set_dados(dados)
                    conversa.estado = 'horarios'

                    return {
                        'success': True,
                        'message':
                        f"Especialidade escolhida: **{esp.nome}** 🩺\n\nVou buscar os horários disponíveis...",
                        'tipo': 'horarios',
                        'proximo_estado': 'horarios'
                    }
            
            # Não conseguiu identificar - mostrar opções
            especialidades_lista = "\n".join([
                f"• **{esp.nome}** - {esp.descricao or 'Especialidade médica'}"
                for esp in especialidades
            ])
            
            return {
                'success': False,
                'message':
                f"Não consegui identificar a especialidade. Por favor, escolha uma das especialidades disponíveis:\n\n{especialidades_lista}\n\nDigite o nome da especialidade desejada:",
                'tipo': 'especialidades',
                'proximo_estado': 'especialidade'
            }

    def _processar_horarios(self, mensagem, conversa, dados):
        """Processa seleção de horário disponível"""
        # Buscar dados da conversa
        local_id = dados.get('local_id')
        especialidade_id = dados.get('especialidade_id')

        if not local_id or not especialidade_id:
            conversa.estado = 'inicio'
            conversa.set_dados({})
            return self._resposta_erro("Erro nos dados. Vamos recomeçar.")

        # Buscar médicos da especialidade
        from database import db
        query = """
            SELECT m.*, h.* FROM medicos m
            JOIN horarios_disponiveis h ON m.id = h.medico_id
            WHERE m.especialidade_id = ? AND h.local_id = ? AND m.ativo = 1 AND h.ativo = 1
        """
        rows = db.execute_query(query, (especialidade_id, local_id))
        
        if not rows:
            return {
                'success': False,
                'message': "Não há horários disponíveis para esta combinação. Escolha outra especialidade ou local.",
                'tipo': 'especialidades',
                'proximo_estado': 'especialidade'
            }

        # Gerar horários disponíveis
        horarios_disponiveis = self._gerar_horarios_disponiveis(rows)
        
        if not horarios_disponiveis:
            return {
                'success': False,
                'message': "Não há horários disponíveis nos próximos dias. Tente novamente mais tarde.",
                'tipo': 'texto',
                'proximo_estado': 'inicio'
            }

        # Tentar interpretar a escolha do usuário
        escolha = self._interpretar_escolha_horario(mensagem, horarios_disponiveis)
        
        if escolha:
            # Salvar escolha e ir para confirmação
            dados.update({
                'medico_id': escolha['medico_id'],
                'medico_nome': escolha['medico_nome'],
                'data_agendamento': escolha['data'],
                'hora_agendamento': escolha['hora'],
                'data_formatada': escolha['data_formatada'],
                'hora_formatada': escolha['hora_formatada']
            })
            conversa.set_dados(dados)
            conversa.estado = 'confirmacao'

            paciente = Paciente.find_by_id(conversa.paciente_id)
            local = Local.find_by_id(local_id)
            especialidade = Especialidade.find_by_id(especialidade_id)

            return {
                'success': True,
                'message': f"📋 **Resumo do Agendamento**\n\n" +
                          f"👤 **Paciente:** {paciente.nome if paciente else 'N/A'}\n" +
                          f"🩺 **Médico:** {escolha['medico_nome']}\n" +
                          f"🏥 **Especialidade:** {especialidade.nome if especialidade else 'N/A'}\n" +
                          f"📍 **Local:** {local.nome if local else 'N/A'}\n" +
                          f"📅 **Data:** {escolha['data_formatada']}\n" +
                          f"⏰ **Horário:** {escolha['hora_formatada']}\n\n" +
                          f"Confirma o agendamento? Digite **'sim'** para confirmar ou **'não'** para cancelar:",
                'tipo': 'confirmacao',
                'proximo_estado': 'confirmacao'
            }
        else:
            # Mostrar horários disponíveis
            horarios_texto = self._formatar_horarios_para_exibicao(horarios_disponiveis)
            
            return {
                'success': True,
                'message': f"📅 **Horários Disponíveis:**\n\n{horarios_texto}\n\n" +
                          f"Digite a **data e horário** desejados (ex: '10/01 às 14:00' ou 'amanhã 9h'):",
                'tipo': 'horarios',
                'horarios': horarios_disponiveis,
                'proximo_estado': 'horarios'
            }

    def _processar_confirmacao(self, mensagem, conversa, dados):
        """Processa confirmação do agendamento"""
        mensagem_lower = mensagem.lower().strip()
        
        if any(palavra in mensagem_lower for palavra in ['sim', 's', 'confirmo', 'ok', 'confirmar']):
            # Confirmar agendamento
            try:
                agendamento = Agendamento.create(
                    paciente_id=conversa.paciente_id,
                    medico_id=dados['medico_id'],
                    especialidade_id=dados['especialidade_id'],
                    local_id=dados['local_id'],
                    data=dados['data_agendamento'],
                    hora=dados['hora_agendamento'],
                    observacoes=""
                )

                conversa.estado = 'finalizado'
                conversa.set_dados({})

                paciente = Paciente.find_by_id(conversa.paciente_id)
                local = Local.find_by_id(dados['local_id'])

                return {
                    'success': True,
                    'message': f"✅ **Agendamento Confirmado!**\n\n" +
                              f"📋 **Número:** #{agendamento.id}\n" +
                              f"👤 **Paciente:** {paciente.nome if paciente else 'N/A'}\n" +
                              f"🩺 **Médico:** {dados['medico_nome']}\n" +
                              f"🏥 **Especialidade:** {dados['especialidade_nome']}\n" +
                              f"📍 **Local:** {local.nome if local else 'N/A'}\n" +
                              f"📅 **Data:** {dados['data_formatada']}\n" +
                              f"⏰ **Horário:** {dados['hora_formatada']}\n\n" +
                              f"📞 Em caso de dúvidas, entre em contato com a clínica.\n\n" +
                              f"Obrigado por usar nosso sistema! 😊",
                    'tipo': 'sucesso',
                    'agendamento_id': agendamento.id,
                    'proximo_estado': 'finalizado'
                }

            except Exception as e:
                logging.error(f"Erro ao criar agendamento: {e}")
                return {
                    'success': False,
                    'message': "Erro ao confirmar agendamento. Tente novamente.",
                    'tipo': 'erro',
                    'proximo_estado': 'horarios'
                }
        
        elif any(palavra in mensagem_lower for palavra in ['não', 'nao', 'n', 'cancelar', 'voltar']):
            # Cancelar e voltar
            conversa.estado = 'horarios'
            return {
                'success': True,
                'message': "Agendamento cancelado. Vou mostrar outros horários disponíveis:",
                'tipo': 'horarios',
                'proximo_estado': 'horarios'
            }
        else:
            # Não entendeu - pedir confirmação novamente
            return {
                'success': False,
                'message': "Não entendi sua resposta. Por favor, digite **'sim'** para confirmar o agendamento ou **'não'** para cancelar:",
                'tipo': 'confirmacao',
                'proximo_estado': 'confirmacao'
            }

    # Continuar com outros métodos auxiliares...
    def _eh_saudacao(self, mensagem):
        """Verifica se é uma saudação"""
        saudacoes = ['oi', 'olá', 'ola', 'hey', 'hello', 'bom dia', 'boa tarde', 'boa noite']
        return any(saudacao in mensagem.lower() for saudacao in saudacoes)

    def _eh_cancelamento(self, mensagem):
        """Verifica se é uma solicitação de cancelamento"""
        palavras_cancelamento = ['cancelar', 'desmarcar', 'remover consulta', 'cancelo', 'cancelamento']
        return any(palavra in mensagem.lower() for palavra in palavras_cancelamento)

    def _extrair_cpf(self, mensagem):
        """Extrai e valida CPF da mensagem"""
        import re
        # Extrair apenas números
        numeros = re.findall(r'\d', mensagem)
        cpf = ''.join(numeros)
        
        # Validar se tem 11 dígitos
        if len(cpf) == 11:
            return cpf
        return None

    def _formatar_cpf(self, cpf):
        """Formata CPF para exibição"""
        if len(cpf) == 11:
            return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        return cpf

    def _extrair_telefone(self, mensagem):
        """Extrai e valida telefone da mensagem"""
        import re
        numeros = re.findall(r'\d', mensagem)
        telefone = ''.join(numeros)
        
        # Validar se tem entre 10 e 11 dígitos
        if len(telefone) >= 10 and len(telefone) <= 11:
            return telefone
        return None

    def _extrair_email(self, mensagem):
        """Extrai e valida email da mensagem"""
        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, mensagem)
        return emails[0] if emails else None

    def _validar_data_nascimento(self, data_str):
        """Valida e converte data de nascimento"""
        try:
            # Tentar diferentes formatos
            formatos = ['%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y']
            for formato in formatos:
                try:
                    data = datetime.strptime(data_str, formato).date()
                    # Verificar se é uma data válida (não no futuro, não muito antiga)
                    hoje = date.today()
                    if data <= hoje and data >= date(1900, 1, 1):
                        return data
                except ValueError:
                    continue
            return None
        except:
            return None

    def _gerar_horarios_disponiveis(self, rows):
        """Gera horários disponíveis a partir dos dados do banco"""
        # Implementação simplificada - você pode expandir conforme necessário
        from datetime import datetime, timedelta
        
        horarios = []
        hoje = datetime.now().date()
        
        # Processar próximos 14 dias
        for i in range(14):
            data_atual = hoje + timedelta(days=i)
            dia_semana = data_atual.weekday()
            
            for row in rows:
                if row['dia_semana'] == dia_semana:
                    # Gerar slots de horário baseado na duração
                    hora_inicio = datetime.strptime(row['hora_inicio'], '%H:%M').time()
                    hora_fim = datetime.strptime(row['hora_fim'], '%H:%M').time()
                    duracao = row['duracao_consulta']
                    
                    # Criar slots
                    slot_atual = datetime.combine(data_atual, hora_inicio)
                    hora_fim_datetime = datetime.combine(data_atual, hora_fim)
                    
                    while slot_atual < hora_fim_datetime:
                        # Verificar se slot não está ocupado
                        if self._verificar_disponibilidade_slot(row['medico_id'], data_atual, slot_atual.time()):
                            horarios.append({
                                'medico_id': row['medico_id'],
                                'medico_nome': row['nome'],
                                'data': data_atual.strftime('%Y-%m-%d'),
                                'hora': slot_atual.time().strftime('%H:%M'),
                                'data_formatada': data_atual.strftime('%d/%m/%Y'),
                                'hora_formatada': slot_atual.time().strftime('%H:%M')
                            })
                        
                        slot_atual += timedelta(minutes=duracao)
        
        return horarios[:10]  # Limitar a 10 horários para não sobrecarregar

    def _verificar_disponibilidade_slot(self, medico_id, data, hora):
        """Verifica se um slot específico está disponível"""
        from database import db
        
        # Verificar agendamentos regulares
        query = """
            SELECT COUNT(*) as count FROM agendamentos 
            WHERE medico_id = ? AND data = ? AND hora = ? AND status = 'agendado'
        """
        result = db.execute_query(query, (medico_id, data.strftime('%Y-%m-%d'), hora.strftime('%H:%M')))
        
        if result and result[0]['count'] > 0:
            return False
        
        # Verificar agendamentos recorrentes
        dia_semana = data.weekday()
        query_recorrente = """
            SELECT COUNT(*) as count FROM agendamentos_recorrentes 
            WHERE medico_id = ? AND dia_semana = ? AND hora = ? AND ativo = 1
            AND data_inicio <= ? AND (data_fim IS NULL OR data_fim >= ?)
        """
        result_recorrente = db.execute_query(query_recorrente, 
                                           (medico_id, dia_semana, hora.strftime('%H:%M'), 
                                            data.strftime('%Y-%m-%d'), data.strftime('%Y-%m-%d')))
        
        if result_recorrente and result_recorrente[0]['count'] > 0:
            return False
            
        return True

    def _interpretar_escolha_horario(self, mensagem, horarios_disponiveis):
        """Interpreta a escolha de horário do usuário"""
        # Implementação simplificada - pode ser expandida com IA
        mensagem_lower = mensagem.lower().strip()
        
        # Tentar encontrar data e hora na mensagem
        import re
        
        # Padrões para data
        data_patterns = [
            r'(\d{1,2})/(\d{1,2})',  # 10/01
            r'(\d{1,2})-(\d{1,2})',  # 10-01
            r'(\d{1,2})\.(\d{1,2})',  # 10.01
        ]
        
        # Padrões para hora
        hora_patterns = [
            r'(\d{1,2}):(\d{2})',    # 14:00
            r'(\d{1,2})h(\d{2})?',   # 14h00 ou 14h
            r'(\d{1,2}) horas?',     # 14 horas
        ]
        
        data_encontrada = None
        hora_encontrada = None
        
        # Buscar data
        for pattern in data_patterns:
            match = re.search(pattern, mensagem)
            if match:
                dia, mes = match.groups()
                try:
                    # Assumir ano atual
                    ano = datetime.now().year
                    data_encontrada = f"{int(dia):02d}/{int(mes):02d}/{ano}"
                    break
                except:
                    continue
        
        # Buscar hora
        for pattern in hora_patterns:
            match = re.search(pattern, mensagem)
            if match:
                if pattern.endswith('horas?'):
                    hora = int(match.group(1))
                    hora_encontrada = f"{hora:02d}:00"
                else:
                    hora = int(match.group(1))
                    minutos = int(match.group(2)) if match.group(2) else 0
                    hora_encontrada = f"{hora:02d}:{minutos:02d}"
                break
        
        # Se encontrou data e/ou hora, tentar fazer match com horários disponíveis
        for horario in horarios_disponiveis:
            match_data = not data_encontrada or data_encontrada.startswith(horario['data_formatada'][:5])
            match_hora = not hora_encontrada or hora_encontrada == horario['hora']
            
            if match_data and match_hora:
                return horario
        
        # Se não encontrou match exato, retornar None para mostrar opções
        return None

    def _formatar_horarios_para_exibicao(self, horarios):
        """Formata horários para exibição ao usuário"""
        if not horarios:
            return "Nenhum horário disponível."
        
        # Agrupar por data
        por_data = {}
        for horario in horarios:
            data = horario['data_formatada']
            if data not in por_data:
                por_data[data] = []
            por_data[data].append(horario)
        
        # Formatar para exibição
        texto = []
        for data, slots in sorted(por_data.items()):
            texto.append(f"📅 **{data}**")
            horarios_do_dia = ", ".join([slot['hora_formatada'] for slot in slots])
            texto.append(f"   {horarios_do_dia}")
            texto.append("")
        
        return "\n".join(texto)

    def _processar_cancelamento_cpf_valido(self, conversa, paciente):
        """Processa cancelamento quando CPF é válido"""
        # Buscar agendamentos ativos do paciente
        agendamentos = [a for a in paciente.get_agendamentos() if a.status == 'agendado']
        
        if not agendamentos:
            return {
                'success': False,
                'message': f"Olá, {paciente.nome}! Você não possui agendamentos ativos para cancelar.\n\nDigite 'oi' se quiser fazer um novo agendamento.",
                'tipo': 'texto',
                'proximo_estado': 'inicio'
            }
        
        # Mostrar agendamentos para escolher qual cancelar
        lista_agendamentos = []
        for i, agendamento in enumerate(agendamentos, 1):
            medico = agendamento.get_medico()
            especialidade = agendamento.get_especialidade()
            local = agendamento.get_local()
            
            lista_agendamentos.append(
                f"{i}. **{medico.nome if medico else 'N/A'}** - {especialidade.nome if especialidade else 'N/A'}\n" +
                f"   📅 {agendamento.to_dict()['data']} às {agendamento.to_dict()['hora']}\n" +
                f"   📍 {local.nome if local else 'N/A'}"
            )
        
        lista_texto = "\n\n".join(lista_agendamentos)
        
        # Salvar agendamentos na conversa para processar escolha
        dados = {'agendamentos_para_cancelar': [a.id for a in agendamentos]}
        conversa.set_dados(dados)
        
        return {
            'success': True,
            'message': f"Olá, {paciente.nome}! 👋\n\nVocê possui {len(agendamentos)} agendamento(s) ativo(s):\n\n{lista_texto}\n\nDigite o **número** do agendamento que deseja cancelar:",
            'tipo': 'cancelamento',
            'agendamentos': [a.to_dict() for a in agendamentos],
            'proximo_estado': 'cancelamento'
        }

    def _processar_consulta_agendamentos_cpf_valido(self, conversa, paciente):
        """Processa consulta de agendamentos quando CPF é válido"""
        agendamentos = paciente.get_agendamentos()
        
        if not agendamentos:
            return {
                'success': True,
                'message': f"Olá, {paciente.nome}! 👋\n\nVocê não possui nenhum agendamento registrado no sistema.\n\nDigite 'agendar' se quiser fazer um novo agendamento.",
                'tipo': 'texto',
                'proximo_estado': 'inicio'
            }
        
        # Separar agendamentos por status
        agendados = [a for a in agendamentos if a.status == 'agendado']
        cancelados = [a for a in agendamentos if a.status == 'cancelado']
        concluidos = [a for a in agendamentos if a.status == 'concluido']
        
        mensagem_partes = [f"Olá, {paciente.nome}! 👋\n\n📋 **Seus Agendamentos:**\n"]
        
        if agendados:
            mensagem_partes.append("✅ **Agendamentos Ativos:**")
            for agendamento in agendados:
                medico = agendamento.get_medico()
                especialidade = agendamento.get_especialidade()
                local = agendamento.get_local()
                mensagem_partes.append(
                    f"• **Dr(a). {medico.nome if medico else 'N/A'}** - {especialidade.nome if especialidade else 'N/A'}\n" +
                    f"  📅 {agendamento.to_dict()['data']} às {agendamento.to_dict()['hora']}\n" +
                    f"  📍 {local.nome if local else 'N/A'}"
                )
            mensagem_partes.append("")
        
        if cancelados:
            mensagem_partes.append("❌ **Agendamentos Cancelados:**")
            for agendamento in cancelados[-3:]:  # Mostrar só os últimos 3
                medico = agendamento.get_medico()
                especialidade = agendamento.get_especialidade()
                mensagem_partes.append(
                    f"• **Dr(a). {medico.nome if medico else 'N/A'}** - {especialidade.nome if especialidade else 'N/A'}\n" +
                    f"  📅 {agendamento.to_dict()['data']} às {agendamento.to_dict()['hora']}"
                )
            mensagem_partes.append("")
        
        if concluidos:
            mensagem_partes.append("✅ **Consultas Realizadas:**")
            for agendamento in concluidos[-3:]:  # Mostrar só os últimos 3
                medico = agendamento.get_medico()
                especialidade = agendamento.get_especialidade()
                mensagem_partes.append(
                    f"• **Dr(a). {medico.nome if medico else 'N/A'}** - {especialidade.nome if especialidade else 'N/A'}\n" +
                    f"  📅 {agendamento.to_dict()['data']} às {agendamento.to_dict()['hora']}"
                )
        
        mensagem_partes.append("\n💬 Digite 'agendar' para fazer um novo agendamento ou 'cancelar' para cancelar algum agendamento ativo.")
        
        conversa.estado = 'finalizado'
        conversa.set_dados({})
        
        return {
            'success': True,
            'message': "\n".join(mensagem_partes),
            'tipo': 'consulta',
            'agendamentos': [a.to_dict() for a in agendamentos],
            'proximo_estado': 'inicio'
        }

    def _processar_cancelamento(self, mensagem, conversa):
        """Processa cancelamento de agendamento"""
        dados = conversa.get_dados() or {}
        
        if 'agendamentos_para_cancelar' in dados:
            # Usuário está escolhendo qual agendamento cancelar
            try:
                numero = int(mensagem.strip())
                agendamentos_ids = dados['agendamentos_para_cancelar']
                
                if 1 <= numero <= len(agendamentos_ids):
                    agendamento_id = agendamentos_ids[numero - 1]
                    agendamento = Agendamento.find_by_id(agendamento_id)
                    
                    if agendamento and agendamento.status == 'agendado':
                        # Cancelar agendamento
                        agendamento.cancelar('Cancelado pelo paciente via chatbot')
                        
                        medico = agendamento.get_medico()
                        especialidade = agendamento.get_especialidade()
                        
                        conversa.estado = 'finalizado'
                        conversa.set_dados({})
                        
                        return {
                            'success': True,
                            'message': f"✅ **Agendamento Cancelado!**\n\n" +
                                      f"🩺 **Médico:** Dr(a). {medico.nome if medico else 'N/A'}\n" +
                                      f"🏥 **Especialidade:** {especialidade.nome if especialidade else 'N/A'}\n" +
                                      f"📅 **Data/Hora:** {agendamento.to_dict()['data']} às {agendamento.to_dict()['hora']}\n\n" +
                                      f"O agendamento foi cancelado com sucesso. Se precisar reagendar, digite 'agendar'.\n\n" +
                                      f"Obrigado! 😊",
                            'tipo': 'sucesso',
                            'proximo_estado': 'finalizado'
                        }
                    else:
                        return {
                            'success': False,
                            'message': "Agendamento não encontrado ou já foi cancelado. Digite um número válido:",
                            'tipo': 'cancelamento',
                            'proximo_estado': 'cancelamento'
                        }
                else:
                    return {
                        'success': False,
                        'message': f"Número inválido. Digite um número entre 1 e {len(agendamentos_ids)}:",
                        'tipo': 'cancelamento',
                        'proximo_estado': 'cancelamento'
                    }
            
            except ValueError:
                return {
                    'success': False,
                    'message': "Por favor, digite apenas o número do agendamento que deseja cancelar:",
                    'tipo': 'cancelamento',
                    'proximo_estado': 'cancelamento'
                }
        else:
            # Ainda precisa do CPF para cancelamento
            return self._processar_cpf(mensagem, conversa)

    def _resposta_erro(self, mensagem):
        """Retorna resposta padrão de erro"""
        return {
            'success': False,
            'message': mensagem,
            'tipo': 'erro',
            'proximo_estado': 'inicio'
        }

# Instância global do serviço
chatbot_service = ChatbotService()