#!/usr/bin/env python3
"""Responde às perguntas do setup conferindo o texto de cada uma (AGENTS.md: nenhuma resposta aprova outra etapa).

Uso: answer.py [--allow-unused] 'TRECHO=RESPOSTA' ... -- COMANDO [ARGS]
Cada pergunta precisa conter o TRECHO seguinte da lista; a RESPOSTA <EOF> fecha a entrada nessa pergunta.
Sai com 98 se uma pergunta não bater, se aparecer pergunta depois do fim da lista ou se sobrar resposta
(salvo com --allow-unused, para respostas que só seriam usadas numa regressão). Sem saída por
ANSWER_TIMEOUT segundos (padrão 60), encerra o comando e sai com 98: uma leitura sem pergunta não trava a suíte.
"""
import os
import re
import select
import subprocess
import sys

PROMPT = re.compile(rb'(\[s/N\] |substituir: |retirar: )$')


def main():
    arguments = sys.argv[1:]
    allow_unused = arguments[:1] == ['--allow-unused']
    arguments = arguments[1:] if allow_unused else arguments
    separator = arguments.index('--')
    expected = [item.split('=', 1) for item in arguments[:separator]]
    timeout = float(os.environ.get('ANSWER_TIMEOUT', '60'))
    child = subprocess.Popen(arguments[separator + 1:], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    buffer, failed = b'', False
    record = os.environ.get('ANSWER_RECORD')
    while True:
        if not select.select([child.stdout], [], [], timeout)[0]:
            child.kill()
            child.wait()
            print(f'\nanswer.py: {timeout:g}s sem saída; o comando esperava algo sem pergunta reconhecida', file=sys.stderr)
            sys.exit(98)
        chunk = os.read(child.stdout.fileno(), 4096)
        if not chunk:
            break
        sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()
        buffer = (buffer + chunk)[-4096:]
        if not PROMPT.search(buffer) or child.stdin.closed:
            continue
        prompt = buffer.rsplit(b'\n', 1)[-1].decode(errors='replace')
        buffer = b''
        if record:
            with open(record, 'a') as stream:
                stream.write(prompt.strip() + '\n')
        if not expected:
            failed = True
            print(f'\nanswer.py: pergunta sem resposta prevista: {prompt!r}', file=sys.stderr)
            child.stdin.close()
            continue
        fragment, answer = expected.pop(0)
        if fragment not in prompt:
            failed, answer = True, 'n'
            print(f'\nanswer.py: pergunta inesperada: {prompt!r}; esperado trecho {fragment!r}', file=sys.stderr)
        if answer == '<EOF>':
            child.stdin.close()
            continue
        child.stdin.write((answer + '\n').encode())
        child.stdin.flush()
    code = child.wait()
    if expected and not allow_unused:
        failed = True
        print(f'\nanswer.py: respostas não usadas: {expected!r}', file=sys.stderr)
    sys.exit(98 if failed else code)


if __name__ == '__main__':
    main()
