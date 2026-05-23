---
claim_id: yt-6d86d06bfc0bfb2d
entity: yt:economia_tokens_Claude_code
type: video_transcript
source_type: youtube
source_ref: desconhecida
retrieved_at: 2026-04-28T22:33:32.111144+00:00
retrieved_by: livy_agent
confidence: high
needs_review: false
draft: false
language: pt-BR
---

# Economia de Tokens no Claude Code

**Canal:** Canal não identificado (português)  
**URL:** desconhecida  
**ID:** economia_tokens_Claude_code

## Transcrição Completa

[00:00:00] Se você usa cloud, esse vídeo vai te
[00:00:02] economizar muito dinheiro. Bater o
[00:00:04] limite da sessão virou um problema
[00:00:05] gigante em toda a comunidade nas últimas
[00:00:08] semanas. Então, nesse vídeo de hoje, eu
[00:00:10] vou te mostrar como garantir que você
[00:00:12] não vai bater o seu limite semanal. Eu
[00:00:14] vou te mostrar as skills para te ajudar
[00:00:16] a gerenciar o limite de sessão. Vou te
[00:00:18] mostrar as ferramentas gratuitas que
[00:00:20] você pode utilizar para reduzir a
[00:00:21] quantidade de tokens que você gasta. E
[00:00:24] também vou te mostrar as melhores
[00:00:25] práticas que Antropic recomenda para
[00:00:28] você não bater o seu limite. Então não
[00:00:30] importa onde você usa cloud ou da forma
[00:00:32] que você utiliza. Esse vídeo de hoje vai
[00:00:34] te ajudar a economizar muito dinheiro.
[00:00:36] Então vamos começar do básico. O que é
[00:00:38] contexto? Contexto é basicamente tudo
[00:00:40] que a cloud consegue ver de uma única
[00:00:43] vez. Isso inclui o system prompt, a
[00:00:45] conversa inteira que vocês tiveram, cada
[00:00:48] ferramenta que ela tem acesso, cada
[00:00:49] ferramenta, cada saída de arquivo, cada
[00:00:52] skill, cada MCP server ou agente no seu
[00:00:55] próprio projeto. O contexto é
[00:00:57] basicamente tudo isso. O Cloud Code nos
[00:00:59] dá 1 milhão de tokens, o que é muita
[00:01:01] coisa, mas antes mesmo de você começar a
[00:01:04] digitar ou dar a primeira instrução pra
[00:01:06] cloud, você já tá queimando em média uns
[00:01:08] 8.000 token só com esse overhead inicial
[00:01:11] da cloud, com coisas como o seu system
[00:01:14] prompt, o cloud.m, seus arquivos de
[00:01:16] contexto, MCP, skills e todo esse tipo
[00:01:19] de coisa. E pode ser muito mais do que
[00:01:22] 8.000, chegando até 60.000 tokens só
[00:01:25] nesse overhead inicial. E aqui vai uma
[00:01:28] dica prática. Se você ainda não fez
[00:01:29] isso, dá barra context dentro do Cloud
[00:01:32] Code e vê quanto você gasta antes de
[00:01:35] iniciar sua sessão. Com esse contexto,
[00:01:37] você talvez consiga encontrar arquivos
[00:01:39] que você pode deletar ou reorganizar ali
[00:01:42] antes de iniciar o seu projeto. Se você
[00:01:44] não fizer isso, você pode estar gastando
[00:01:46] muitos tokens invisíveis ali sem você
[00:01:49] nem imaginar. E como os tokens realmente
[00:01:52] funcionam, que é uma coisa muito
[00:01:53] importante que você tem que entender
[00:01:55] sobre como os tokens da cloud funcionam.
[00:01:57] E essa única coisa já economizou
[00:01:59] centenas de milhares de tokens para
[00:02:01] várias pessoas ao redor do mundo. Um
[00:02:03] token é a menor unidade de texto que o
[00:02:06] modelo de ler e te cobra por isso. Mais
[00:02:08] ou menos o token é igual a uma palavra.
[00:02:10] Então toda vez que você manda uma nova
[00:02:12] mensagem com um chat extenso pra cloud,
[00:02:15] ela relê todo o histórico novamente. Ela
[00:02:17] vai reler a sua conversa inteira e tudo
[00:02:19] isso são tokens que ela vai te cobrar.
[00:02:22] Então ele lê a sua mensagem inicial e
[00:02:24] depois quando você responde ele, ele lê
[00:02:26] novamente a mensagem inicial, a resposta
[00:02:28] dele, a sua resposta e assim
[00:02:30] sucetivamente até a sua última instrução
[00:02:32] mais recente. E ele faz isso todas as
[00:02:35] vezes. Isso significa que enquanto você
[00:02:37] tá ali conversando com a Cláudia, o seu
[00:02:39] custo cresce de forma composta. Ele não
[00:02:41] tá só somando, ele tá crescendo
[00:02:43] exponencialmente. Então a mensagem um
[00:02:45] custa 500 tokens e a mensagem 30 custa
[00:02:49] 15.000 porque ele tá relendo todas as 30
[00:02:52] mensagens anteriores. Um desenvolvedor
[00:02:54] rastreou um chat com mais de 100
[00:02:56] mensagens e ele descobriu que 98,5%
[00:03:00] dos gastos de token dessas mensagens
[00:03:03] eram gastos só com a cloud relendo o
[00:03:05] histórico. E isso é um desperdício
[00:03:08] inimaginável. É óbvio que ela precisa
[00:03:10] entender o que a gente tá fazendo e ter
[00:03:11] o contexto da conversa, só que 98,5%
[00:03:15] é muita coisa, né? E agora o context
[00:03:18] hot. O que é o context hot? Ele acontece
[00:03:21] quando a sua sessão cresce e o
[00:03:23] desempenho do modelo LLM cai, porque a
[00:03:26] atenção dele fica espalhada por vários
[00:03:29] tokens e por cada mensagem que já foi
[00:03:32] enviada. Com certeza você já deve ter
[00:03:34] notado isso utilizando a cloud. Ela
[00:03:37] começa a se distrair, começa a esquecer
[00:03:39] coisas que já foram faladas, começa a se
[00:03:42] contradizer, editar arquivos sem você
[00:03:44] pedir ou sem ela ler antes, ela fica
[00:03:47] notavelmente muito pior. As estatísticas
[00:03:49] mostram que a precisão do retrival cai
[00:03:52] de 92%
[00:03:54] em 250.000 tokens para 78% em 1 milhão
[00:03:59] de tokens. Então, mesmo que você por
[00:04:01] acaso consiga preencher essa janela de 1
[00:04:03] milhão de tokens conversando com a
[00:04:05] Cloud, o desempenho do modelo vai est
[00:04:07] muito pior e ela não vai conseguir achar
[00:04:09] o que você busca dentro dessa janela. E
[00:04:12] conforme o modelo piora, os seus gastos
[00:04:14] de tokens aumenta, porque com a LLM
[00:04:17] pior, você gera um output ali que te
[00:04:19] gasta 500.000 tokens. E se ela tivesse
[00:04:22] desempenhando da maneira correta,
[00:04:23] poderia gastar 100 ou 200.000.
[00:04:26] Autocompação. O que é e por ela é uma
[00:04:29] silada? A autocompactação ativa
[00:04:32] automaticamente e ela é ativada por
[00:04:34] volta de 95% da sua janela de contexto,
[00:04:38] mas muita gente relata que é tarde
[00:04:41] demais isso. E quando ocorre essa
[00:04:44] autocompactação, você fica só com 20 a
[00:04:47] 30% dos detalhes originais. você tá
[00:04:50] perdendo muito contexto e o modelo tá
[00:04:52] fazendo essa autocompactação no pior
[00:04:54] momento de inteligência dele, porque a
[00:04:56] autocompactação acontece exatamente no
[00:04:59] momento do context hot que a gente
[00:05:01] acabou de conversar sobre. E aqui uma
[00:05:03] analogia, imagina que você tá fazendo
[00:05:06] uma mala pra viagem. Se você faz essa
[00:05:08] mala na noite anterior, você tem tempo
[00:05:10] para pensar a se planejar e você não
[00:05:12] esquece de levar nada porque você tem
[00:05:14] tempo de fazer uma lista e conferir. Mas
[00:05:17] se você acordou atrasado e precisa fazer
[00:05:19] essa mala muito rápido, você com certeza
[00:05:22] vai esquecer de algumas coisas. Isso
[00:05:24] basicamente é o que a autocompactação é.
[00:05:27] E a solução para esse problema seria
[00:05:29] fazer essa autocompactação entre 50 a
[00:05:32] 60% da janela de contexto, onde a LLM
[00:05:36] ainda tem um desempenho legal e consegue
[00:05:38] ali fazer bem essa compactação. As cinco
[00:05:42] opções depois de cada resposta que
[00:05:44] Antropic libera pra gente. Toda vez que
[00:05:46] a cloud responde, você tem basicamente
[00:05:48] essas cinco opções. A opção um é a
[00:05:50] continuar, onde você só responde e manda
[00:05:53] outra mensagem. o barra rewind, onde
[00:05:56] você volta paraa mensagem anterior e
[00:05:59] exclui tudo depois dela. O barra clear
[00:06:02] começar tudo do zero de novo. O barraca
[00:06:05] compact resume a sessão e substitui o
[00:06:07] histórico por esse resumo. E na opção
[00:06:10] cinco, você tem a opção de delegar para
[00:06:12] um subagente, onde você manda essa
[00:06:14] tarefa para uma janela de contexto nova
[00:06:17] e recebe de volta só o resultado final.
[00:06:19] barrewind, o hábito número um
[00:06:22] recomendado pela própria antropic. Você
[00:06:24] pode ativar ele apertando duas vezes o
[00:06:27] botão de ES ou enviando para
[00:06:29] cloud/rewind.
[00:06:31] E isso te deixa pular para qualquer
[00:06:32] mensagem anterior da sessão atual. E aí
[00:06:35] tudo a partir dessa mensagem vai ser
[00:06:38] excluído e isso é muito bom pro seu
[00:06:40] contexto. Essa função de barra reenwide
[00:06:42] é muito mais útil do que parece, porque
[00:06:44] na maioria das vezes quando Cloud faz
[00:06:46] algo errado, a gente tem o costume de
[00:06:48] falar para ela: "Pare de fazer isso, é,
[00:06:50] eu não gostei, quero que você siga por
[00:06:51] esse caminho." E aí a Cloud se confunde
[00:06:53] e tenta várias coisas diferentes e ela
[00:06:56] pode até fazer funcionar, só que tudo
[00:06:58] isso vai ficar salvo e vai ficar ali
[00:07:02] guardado no seu contexto. Todas as vezes
[00:07:04] que falharem novamente, que você errar
[00:07:07] algum comando, a cloud seguir por um
[00:07:08] caminho errado, vai ficar salvo ali,
[00:07:10] consumindo espaço no seu contexto, o que
[00:07:13] contribui para o aumento da sua janela
[00:07:15] de token, poluindo as suas respostas
[00:07:18] futuras e o desempenho da cloud até o
[00:07:20] final da janela de contexto. O barra
[00:07:22] real wide é muito melhor porque o seu
[00:07:24] contexto fica limpo. E quando você dá
[00:07:25] barra wide, você ainda tem uma opção
[00:07:28] chamada summarize from here, que
[00:07:30] basicamente cria uma mensagem de
[00:07:32] handoff, tipo uma nota da cloud do
[00:07:35] passado pra cloud do futuro, falando
[00:07:37] onde elas erraram e como não cometer
[00:07:40] esse erro no futuro. E aqui uma técnica
[00:07:42] que você pode utilizar quando você
[00:07:45] perceber que o desempenho da cloud tá
[00:07:46] piorando, onde você tá atingindo ali uma
[00:07:50] porcentagem legal da sua janela de
[00:07:52] contexto. Você pode pedir um resumo de
[00:07:54] tudo que foi conversado até aquele
[00:07:56] momento. E aí a cloud te enviando esse
[00:07:58] resumo, você guarda ele, dá um barra
[00:08:01] clear, onde vai limpar todo o contexto e
[00:08:04] aí você cola o resumo novamente e você
[00:08:07] fala para ela que é um resumo e que quer
[00:08:09] continuar a partir dali. Assim você vai
[00:08:11] resetar a janela de contexto e ainda
[00:08:13] assim vai ter a cloud por dentro do que
[00:08:15] vocês estavam construindo. E agora os
[00:08:17] suagentes. Cada subagente da cloud ganha
[00:08:20] uma janela de contexto nova. Ele faz o
[00:08:22] trabalho dele, as pesquisas, junta os
[00:08:24] resultados e manda de volta paraa sua
[00:08:27] sessão principal com um único output. E
[00:08:29] você pode dar as instruções
[00:08:31] explicitamente paraa cloud. Você pode
[00:08:33] pedir, por exemplo, sobe um subagente
[00:08:36] para revisar o nosso código, sobe um
[00:08:38] subagente para fazer um resumo da sessão
[00:08:40] e cada subagente pode utilizar um modelo
[00:08:43] mais barato do que o atual que você tá
[00:08:45] utilizando. Então, se você tá
[00:08:47] desenvolvendo com o Sone 4.6, você pode
[00:08:50] utilizar o Haiku para fazer uma
[00:08:52] pesquisa. É só você dar essa instrução
[00:08:54] explicitamente pra cloud. Você diz para
[00:08:56] ela sobe um suagente para fazer um
[00:08:58] resumo da nossa sessão atual, mas
[00:09:01] garanta que seja o haiku quem está
[00:09:03] fazendo esse resumo. E o que vai
[00:09:05] acontecer é que você vai economizar, né,
[00:09:07] bastante token e o resultado da tarefa
[00:09:10] vai ficar muitas vezes igual do que você
[00:09:13] tivesse utilizado o modelo mais caro. E
[00:09:16] aqui outra dica, fica de olho no seu
[00:09:18] limite da sessão. Se você tiver muito
[00:09:20] perto de atingir esse limite, né, você
[00:09:23] tiver ali com 50% ali da sessão, mas
[00:09:27] faltam apenas uma hora para resetar, né,
[00:09:30] e zerar ali, você ter a todo o limite
[00:09:32] novamente, aí você deve abusar, né, e
[00:09:35] trabalhar ali em um código mais pesado.
[00:09:37] Então você, né, faz um trabalho que você
[00:09:40] tá adiando e aproveita essa esse gap,
[00:09:44] né, que você tem até estourar ali o
[00:09:47] limite da sessão, porque já vai resetar
[00:09:49] mesmo. E se por acaso você tiver muito
[00:09:51] perto ali de bater o seu limite e faltar
[00:09:54] muitas horas ali ainda pra resetar, né,
[00:09:57] e você vai ficar muito tempo sem
[00:09:59] conseguir codar, sem conseguir mexer no
[00:10:01] seu projeto, então faz uma pausa, né?
[00:10:03] Não utiliza o cloud ali ou utiliza para
[00:10:06] tarefas mais simples, como só conversar,
[00:10:08] responder algumas coisas. Então, espera
[00:10:10] ficar mais perto de resetar o seu limite
[00:10:12] da sessão para que você não fique sem o
[00:10:15] limite. Sempre converta tudo pra MarkD.
[00:10:18] O MarkD é muito mais rápido e muito mais
[00:10:20] barato para os modelos de LLM. Se você
[00:10:23] trabalhar com MarkDAL, com elas, você
[00:10:25] vai ter uma redução absurda nos seus
[00:10:26] tokens. Então, de HTML para MarkD, a
[00:10:29] gente tem mais ou menos 90% de redução
[00:10:32] de gasto de token. De PDF para MarkD a
[00:10:35] gente já tem 67%.
[00:10:38] E de doc para Mark a gente tem uma
[00:10:40] redução de mais ou menos 33%. Isso
[00:10:43] significa que você consegue colocar mais
[00:10:45] ou menos três vezes mais conteúdo na
[00:10:49] mesma janela de contexto. Um PDF de 40
[00:10:52] páginas pode ocupar o mesmo espaço de um
[00:10:55] markdow de 130 páginas. Você pode
[00:10:58] utilizar ferramentas, como por exemplo o
[00:11:00] Doc Link para fazer esse tipo de
[00:11:02] conversão. Isso acontece porque os
[00:11:04] agentes processam textos de forma muito
[00:11:07] mais simples e o PDF, o doc e o HTML tem
[00:11:11] todo o ruído por trás. layout, metadata
[00:11:14] e formatação que o agente de A precisa
[00:11:16] lhe dar. E na verdade tudo que o modelo
[00:11:18] precisa é do conteúdo que tá dentro
[00:11:21] desse documento. Então a gente pode
[00:11:23] extrair ele com o MarkD. Se o seu
[00:11:25] conteúdo é só baseado em texto, você
[00:11:27] transcreve MarkDW e entrega pra cloud.
[00:11:30] Barrabtw.
[00:11:31] Ele serve para perguntas rápidas sem
[00:11:34] poluir o seu contexto. Então você
[00:11:36] utiliza o barra BTW e isso vai abrir ali
[00:11:38] um overlay para perguntas paralelas ao
[00:11:41] seu projeto que não vão ficar salvas no
[00:11:44] seu histórico de conversa. Então, se
[00:11:45] você tá ali muito profundo, né, num
[00:11:48] projeto muito avançado e quer fazer uma
[00:11:49] pergunta ali que não tem nada a ver com
[00:11:52] que vocês estão construindo, dá esse
[00:11:54] barraptwar
[00:11:56] e conversar com a cloud e o seu contexto
[00:11:58] ainda se mantém limpo. Planeje primeiro
[00:12:00] e implemente uma única vez. O Boris
[00:12:03] Cherney, o dono da cloud, começa toda a
[00:12:05] sessão no modo de planejamento. A ideia
[00:12:08] é o seguinte, se você gasta tokens no
[00:12:10] começo para ficar claro sobre o que é o
[00:12:13] seu projeto e o que vocês estão fazendo
[00:12:15] antes de já começar a construir, você
[00:12:17] não vai precisar corrigir depois e no
[00:12:19] fim das contas sai bem mais barato ao
[00:12:22] longo do tempo se a gente for levar em
[00:12:24] conta a eficiência dos tokens. Então
[00:12:26] você deve começar pelo modo de
[00:12:28] planejamento, acertar ele e depois
[00:12:31] deixar Cloud fazer a implementação de
[00:12:32] uma única vez, porque ele já entendeu o
[00:12:35] que ele precisa fazer e o que você quer.
[00:12:37] Disciplina do Cloud MD. Não dá para
[00:12:39] passar por um vídeo de tokens sem falar
[00:12:42] sobre a disciplina do cloud MD. Sempre
[00:12:44] mantenha esse arquivo com menos de 200
[00:12:47] linhas, que seriam basicamente 2000
[00:12:49] tokens, porque ele carrega em toda
[00:12:51] sessão. Então, se ele estiver inchado,
[00:12:53] você pega esse inchaço em todas as
[00:12:55] conversas que vocês tiverem. É um espaço
[00:12:58] limitado, então coloca lá dentro só o
[00:13:00] que é realmente útil e o que você
[00:13:02] realmente precisa que a cloud saiba para
[00:13:04] que ela consiga fazer o trabalho da
[00:13:06] maneira correta. Outras alternativas
[00:13:08] inteligentes são utilizar as skills como
[00:13:12] maneiras ali da cloud ativar só quando é
[00:13:14] realmente necessário. Então você não
[00:13:16] precisa colocar ali no cloud.md. E se
[00:13:19] você tem um repositório gigante, você
[00:13:21] pode usar o ponto cloud ignor. Assim
[00:13:24] você vai excluir pastas e arquivos que
[00:13:26] você não quer que a cloud leia para não
[00:13:28] gastar tanto token. Os tokens de saída
[00:13:31] gastam muito mais do que os tokens de
[00:13:33] entrada. Muita gente pensa que é o
[00:13:36] contrário, mas na verdade não. Existem
[00:13:38] muitos tokens de saída que são gastos e
[00:13:41] você nem consegue ver. Então é
[00:13:43] importante você entender que além dos
[00:13:46] tokens ali que você consegue analisar,
[00:13:48] como o tamanho do texto que a Cloud te
[00:13:50] mandou, o tempo que ela ficou pensando,
[00:13:51] existem muitos mais tokens que são
[00:13:53] gastos por trás que você não tem acesso.
[00:13:57] Então não adianta você pedir paraa cloud
[00:13:59] ser comcisa, não vai modificar o tanto
[00:14:03] de gasto que você vai ter com o token de
[00:14:05] saída. E uma estatística aqui para
[00:14:07] vocês. O usuário foi do gasto de 345
[00:14:12] por mês para 42.000 000 por mês. E a
[00:14:16] qualidade do outp ficou exatamente
[00:14:19] igual, com o mesmo trabalho, os mesmos
[00:14:21] resultados, mas por conta dos maus
[00:14:24] hábitos com os tokens, o custo explodiu.
[00:14:26] Janela maior não significa um out
[00:14:29] melhor, só significa mais espaço pra
[00:14:32] context hot e mais espaço pro modelo se
[00:14:35] distrair. Os primeiros 0 a 20% da sua
[00:14:39] janela de contexto são os momentos
[00:14:41] perfeitos. é quando o cloud. MD tá mais
[00:14:44] fresco e o modelo tem o melhor
[00:14:46] desempenho possível. Então, na hora que
[00:14:47] você for utilizar a cloud, tenta atingir
[00:14:50] os seus 200.000 1000 gastos de token ali
[00:14:53] na sua janela de contexto. Realmente
[00:14:55] necessário você tenta tingir essa janela
[00:14:57] de 1 milhão, mas correndo o risco, né,
[00:15:00] de acabar acontecendo o contact,
[00:15:04] porque quanto mais janela de contexto
[00:15:06] você tem, mais chances de criar hábitos
[00:15:09] piores que vão fazer você gastar mais
[00:15:11] tokens, você também tem. Então muda pra
[00:15:14] janela de 1 milhão só se realmente for
[00:15:16] necessário. Você tem um projeto grande,
[00:15:18] não faz tudo em uma sessão única. Você
[00:15:21] pode encadeiar ela. Você pode, por
[00:15:23] exemplo, separar uma sessão onde onde é
[00:15:26] uma sessão de descoberta, onde a Clou
[00:15:28] vai ler PDFs, lê o Code base e te
[00:15:31] entrega um doc bem feito. E aí você pega
[00:15:33] esse doc e move para uma sessão de
[00:15:35] planejamento, onde a Cloud lê e cria o
[00:15:38] plano para vocês. E aí você pega esse
[00:15:40] plano finalizado e ali perfeito e move
[00:15:43] pra sessão de execução para dar início
[00:15:46] realmente no seu projeto. E aí cada
[00:15:48] sessão tem uma tarefa especializada e
[00:15:51] você consegue extrair o melhor
[00:15:52] desempenho delas. Enfim, esse foi o
[00:15:54] vídeo de hoje. Muito obrigado por
[00:15:56] assistir até aqui. Eu te garanto que se
[00:15:58] você utilizar tudo o que foi mostrado
[00:16:00] para você nesse vídeo, você vai extrair
[00:16:02] o melhor desempenho possível da cloud e
[00:16:05] vai usar ela de forma muito mais
[00:16:07] profissional do que a maioria das
[00:16:09] pessoas utilizam hoje em dia. Você tem
[00:16:12] interesse em automatizar o seu negócio
[00:16:14] com inteligência artificial, desde os
[00:16:16] processos internos, o atendimento no
[00:16:18] WhatsApp com uma automação profissional
[00:16:20] e escalável que aguenta ali a demanda,
[00:16:24] entra em contato comigo, eu vou deixar o
[00:16:26] link aqui na descrição. Você só precisa
[00:16:28] clicar e depois vai abrir ali a minha
[00:16:30] lente pagó só clica em entrar em contato
[00:16:33] e vai direto pro meu WhatsApp. Comenta
[00:16:35] aqui embaixo o que vocês gostariam de
[00:16:37] ver sobre a cloud, dicas sobre NN,
[00:16:40] também agentes de automação. Eu vou ler
[00:16:42] todos os comentários aqui e pegar uma
[00:16:44] ideia para gravar o próximo vídeo.
[00:16:46] Enfim, esse foi o vídeo. Muito obrigado.
[00:16:48] Até a próxima. Yeah.

---

## Resumo (TLDR)

Vídeo em português sobre **economia de tokens no Claude Code**:

1. **Contexto**: System prompt + conversa + ferramentas + skills + MCP = tokens gastos antes mesmo de digitar
   - Overhead inicial: 8.000–60.000 tokens (mesmo antes de qualquer instrução)

2. **Custo composto**: A cada mensagem, o modelo relê TODO o histórico
   - Mensagem 1 = 500 tokens; Mensagem 30 = 15.000 tokens (re-lê todas)
   - 98,5% dos tokens gastos são só relendo histórico

3. **Context Hot**: Janela grande = desempenhocai (precisão retrieval cai de 92% para 78%)
   - Auto-compactação ativada em 95% da janela → perde 70-80% dos detalhes
   - Melhor momento para compactar: 50-60% da janela

4. **5 opções pós-resposta**: /continue, /rewind, /clear, /compact, /subagent
   - **/rewind** = voltar e apagar tudo depois (mais subestimado)
   - **Subagentes**: janela nova, modelo barato (ex: Haiku para resumo), resultado final em 1 output

5. **Boas práticas**:
   - Tudo em Markdown (HTML→MD = -90% tokens; PDF→MD = -67%; DOC→MD = -33%)
   - CLAUDE.md < 200 linhas (2000 tokens por sessão)
   - Usar .claudeignore para excluir arquivos grandes
   - Trabalhar em Cadeia: descoberta → planejamento → execução (3 sessões separadas)
   - Respeitar % da janela: 0-20% é zona ótima
   - /btw para perguntas paralelas sem poluir contexto
   - Barra Planning Mode antes de implementar

6. **Output tokens**: Custam mais que input tokens. 345 USD → 42.000 USD/mês por maus hábitos (mesma qualidade).
