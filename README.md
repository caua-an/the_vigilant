# The Vigilant

Um guardião de foco para Linux/X11: tarefas locais, aplicativos minimizados e bloqueio de domínios no Brave. A sessão é iniciada manualmente; terminar todas as tarefas pendentes ou encerrá-la libera os bloqueios.

## Iniciar

Requisitos: Python 3 com Tkinter, `xdotool` e `xprop`, sessão X11 e Brave. No Zorin OS verificado, eles já estão disponíveis. Caso faltem, no Ubuntu/Zorin instale com `sudo apt install python3-tk xdotool x11-utils`.

```sh
cd /home/caua/Documentos/code_projects/the-vigilant
python3 main.py
```

Clique no robô para voltar à janela principal. Em **Tarefas**, selecione uma tarefa e use **Concluir / reabrir**. Excluir a última tarefa não termina a sessão. Em **Sites** e **Aplicativos**, escolha o que deseja deixar em pausa; tudo começa desmarcado. As alterações são salvas localmente em `~/.local/share/the-vigilant/data.json` (ou em `$XDG_DATA_HOME/the-vigilant/data.json`). Não há conta, câmera, microfone nem histórico de navegação.

## Instalar a extensão do Brave

1. Abra `brave://extensions` no perfil desejado e ative **Modo do desenvolvedor**.
2. Clique em **Carregar sem compactação** e escolha a pasta `extension` dentro deste projeto.
3. Mantenha a extensão ativada. Em janelas privadas, habilite **Permitir em modo privado** nas opções da extensão, se desejar. Outros perfis precisam de instalação própria.
4. Inicie uma sessão no aplicativo e confira se aparece **Brave: extensão conectada**. Teste um domínio selecionado numa aba normal.

A extensão consulta o aplicativo no endereço local `127.0.0.1:47653` e usa regras de sessão do navegador. As regras abrangem o domínio informado e seus subdomínios. O prefixo `www.` é removido automaticamente; para outros subdomínios, informe o domínio principal se desejar bloqueá-lo por inteiro. Abas já abertas são substituídas por uma página de aviso e não são restauradas automaticamente.

Após encerrar a sessão, a atualização pode levar alguns segundos. Se o aplicativo for encerrado inesperadamente, a extensão tenta remover as regras quando detectar a desconexão. O Brave pode suspender a extensão em segundo plano; nesse caso a recuperação pode demorar até o próximo alarme (aproximadamente 30 segundos). Uma extensão desativada, outro navegador ou um perfil sem a extensão não estarão protegidos. O aplicativo é uma ajuda ao foco, não uma barreira inviolável.

## Aplicativos e limitações

O monitoramento verifica a janela ativa a cada meio segundo e a minimiza quando a classe da janela ou o nome do processo corresponde ao identificador escolhido. Isso não fecha o programa nem impede seu lançamento. Alguns aplicativos empacotados ou iniciadores não expõem uma classe que corresponda ao nome da lista: nesses casos, adicione manualmente a classe ou o nome do processo. Para descobrir a classe, execute `xprop WM_CLASS` em um terminal e clique na janela desejada. Em Wayland, a identificação e minimização de janelas não são garantidas.

## Verificação

```sh
python3 -m unittest -v
```
