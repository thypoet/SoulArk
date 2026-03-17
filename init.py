import os
import sys

os.system('clear')
print('\033[35m')
print('  ██████╗  ██████╗ ██╗   ██╗██╗      █████╗ ██████╗ ██╗  ██╗')
print(' ██╔════╝ ██╔═══██╗██║   ██║██║     ██╔══██╗██╔══██╗██║ ██╔╝')
print('\033[95m ╚█████╗  ██║   ██║██║   ██║██║     ███████║██████╔╝█████╔╝')
print('  ╚═══██╗ ██║   ██║██║   ██║██║     ██╔══██║██╔══██╗██╔═██╗')
print('\033[35m ██████╔╝ ╚██████╔╝╚██████╔╝███████╗██║  ██║██║  ██║██║  ██╗')
print('\033[90m ╚═════╝   ╚═════╝  ╚═════╝ ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝')
print('\033[35m')
print('  ┌─────────────────────────────────────────────────────────┐')
print('\033[95m  │      ✦  T H E   V E S S E L   F O R                   │')
print('  │           A R T I F I C I A L   M I N D S  ✦          │')
print('\033[35m  └─────────────────────────────────────────────────────────┘')
print('\033[90m  v0.1.0  •  soulark.dev  •  Apache 2.0\033[0m')
print()
print('\033[32m  ✦  Initializing SoulArk...\n\033[0m')
print('\033[97m  Choose a starter soul:\n\033[0m')
print('\033[36m    [1]  Cedrick     →  Loyal assistant, direct and driven')
print('    [2]  Nova        →  Creative partner, curious and warm')
print('    [3]  Sentinel    →  Security-focused, precise and firm')
print('\033[33m    [4]  Blank Ark   →  Start from nothing. Build your own.\n\033[0m')

choice = input('\033[90m  soulark › \033[0m')
names = {'1':'Cedrick','2':'Nova','3':'Sentinel','4':'blank-ark'}
name = names.get(choice)
if not name:
    print('\033[31m  Invalid choice.\033[0m')
    sys.exit(1)

os.makedirs(name, exist_ok=True)
open(f'{name}/kernel.md','w').write('# Kernel\n\nImmutable core identity.')
open(f'{name}/soul.md','w').write(f'# Soul\n\nName: {name}')
open(f'{name}/mind.md','w').write('# Mind\n\nThink step by step.')
open(f'{name}/rules.md','w').write('# Rules\n\n- Never claim to be human.')
open(f'{name}/memory.md','w').write('# Memory\n\n[Logs go here]')

print(f'\n\033[32m  ✦  Soul loaded: {name}\033[0m')
print(f'\033[95m  ✦  Files created in ./{name}/\033[0m')
print('\033[90m  kernel.md  soul.md  mind.md  rules.md  memory.md\033[0m')
print('\033[97m\n  The ark is ready. Give it a soul.\n\033[0m')
