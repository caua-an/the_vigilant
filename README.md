# The Vigilant

Um guardião de foco para Linux/X11: tarefas locais, aplicativos minimizados e bloqueio de domínios por extensão de navegador. A sessão é iniciada manualmente; terminar todas as tarefas pendentes ou encerrá-la libera os bloqueios.

## Iniciar

Requisitos: Python 3 com Tkinter, `xdotool` e `xprop`, sessão X11 e um navegador compatível. No Ubuntu/Zorin, instale os componentes necessários com `sudo apt install python3-tk xdotool x11-utils`.

```sh
cd /home/caua/Documentos/code_projects/the-vigilant
python3 main.py
```

Para criar um atalho no menu de aplicativos apenas para o usuário atual, execute `python3 install_launcher.py`. Se mover a pasta do projeto, remova `~/.local/share/applications/the-vigilant.desktop` (ou `$XDG_DATA_HOME/applications/the-vigilant.desktop`) e execute o comando novamente. O instalador não sobrescreve atalhos existentes diferentes.

Clique no robô para voltar à janela principal ou arraste-o para mover; a posição é salva para as próximas sessões. Em **Tarefas**, selecione uma tarefa e use **Concluir / reabrir**. Excluir a última tarefa não termina a sessão. Em **Sites** e **Aplicativos**, escolha o que deseja deixar em pausa; tudo começa desmarcado. As alterações são salvas localmente em `~/.local/share/the-vigilant/data.json` (ou em `$XDG_DATA_HOME/the-vigilant/data.json`). Não há conta, câmera, microfone nem histórico de navegação.

Em **Customização**, escolha as cores do metal, visor e olhos; restaure as cores originais sem apagar suas frases. O som pode ser desligado e o modo adulto é opcional. Adicione frases normais ou adultas de até 90 caracteres; frases adultas só são sorteadas quando o modo adulto está ativo. Quando ocorrer um bloqueio, o robô fica com olhos vermelhos e mostra uma frase por cerca de dois segundos, sem se mover.

## Instalar a extensão do navegador

**Brave, Chrome e Chromium** (versões 121 ou posteriores):

1. Abra `brave://extensions` no Brave ou `chrome://extensions` no Chrome/Chromium e ative **Modo do desenvolvedor**.
2. Clique em **Carregar sem compactação** e escolha a pasta `extension` dentro deste projeto. Repita em cada navegador e perfil desejado.
3. Inicie uma sessão e verifique o indicador correspondente no aplicativo. Teste um domínio selecionado numa aba normal.

**Firefox** (versão 128 ou posterior): abra `about:debugging#/runtime/this-firefox`, clique em **Carregar extensão temporária** e selecione `extension/manifest.json`. A instalação temporária precisa ser refeita depois de reiniciar o Firefox. Esta integração ainda precisa ser validada em uma instalação real do Firefox.

As extensões de navegadores abertos simultaneamente recebem a mesma configuração. Os indicadores mostram uma comunicação recente, **não comprovam que as regras foram aplicadas**. Janelas privadas estão fora do escopo; perfis sem a extensão não são protegidos.

A extensão consulta o aplicativo no endereço local `127.0.0.1:47653` e usa regras de sessão do navegador. As regras abrangem o domínio informado e seus subdomínios. O prefixo `www.` é removido automaticamente; para outros subdomínios, informe o domínio principal se desejar bloqueá-lo por inteiro. Abas já abertas são substituídas por uma página de aviso e não são restauradas automaticamente.

Para manter um subdomínio acessível, adicione-o em **Sites → Exceções permitidas**. Por exemplo, bloqueie `youtube.com` e adicione `music.youtube.com` como exceção para permitir o YouTube Music. A exceção também libera os subdomínios dela e prevalece sobre todos os bloqueios. Após atualizar o projeto, recarregue a extensão em cada navegador e reinicie o aplicativo.

Após encerrar a sessão, a atualização pode levar algum tempo. Se o aplicativo for encerrado inesperadamente, a extensão tenta remover as regras quando detectar a desconexão. O navegador pode suspender a extensão em segundo plano; nesse caso a recuperação depende de ela voltar a executar. Uma extensão desativada, outro navegador ou um perfil sem a extensão não estarão protegidos. O aplicativo é uma ajuda ao foco, não uma barreira inviolável.

## Windows no futuro

O Windows ainda **não é suportado**. A interface Tkinter, os dados e a extensão podem orientar uma versão futura, mas monitoramento de aplicativos, recorte da janela, som, local dos dados e instalação precisam de adaptações e testes específicos. Não é necessário instalar componentes para Windows nesta versão Linux.

## Aplicativos e limitações

O monitoramento verifica a janela ativa a cada meio segundo e a minimiza quando a classe da janela ou o nome do processo corresponde ao identificador escolhido. Isso não fecha o programa nem impede seu lançamento. Busque aplicativos pelo nome em **Escolher instalado**. Alguns aplicativos empacotados ou iniciadores não expõem uma classe que corresponda ao identificador encontrado e podem não ser detectados. Em Wayland, a identificação e minimização de janelas não são garantidas.

## Verificação

```sh
python3 -m unittest -v
node test_extension.cjs  # opcional: simula os três navegadores; requer Node.js
```
