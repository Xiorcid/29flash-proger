def drawhex(file, type=1):
    text = ""
    if type:
        with open(file, 'rb') as file:
            s = file.read()
    else:
        s = file.read()
    h = ''
    text = ' ' * 10 + ' '.join([f'{h}0{hex(i)[2:]}' for i in range(16)]) + '\n'
    num_steps = len(s) // 16
    for i in range(num_steps):
        sect_s = s[i * 16: (i + 1) * 16]  # a = slice(i *16 : (i + 1)*16)
        new_s = '{:0>6}'.format(hex(i * 16)[2:]) + '    '
        for j in sect_s:
            if len(hex(j)[2:]) == 1 and hex(j)[0].isalpha:
                new_s += f'0{hex(j)[2:]} '
            elif len(hex(j)[2:]) == 1:
                new_s += f'{hex(j)[2:]} '
            else:
                new_s += f'{hex(j)[2:]} '
        new_s += '    '
        for j in sect_s:
            new_s += chr(j) if chr(j).isprintable() else '.'
        text += new_s +"\n"
        if i == num_steps - 1 and len(s) % 16 != 0:
            sect_s = s[(i + 1) * 16:]
            new_s = '{:0>6}'.format(hex((i + 1) * 16)[2:]) + '    '
            for j in sect_s:
                new_s += f'{hex(j)[2:]} '
            new_s += ' ' * ((16 * 3 + 3) - len(new_s) + 11)
            for j in sect_s:
                new_s += chr(j) if chr(j).isprintable() else '.'
            text += new_s + "\n"
    print(text)
    return text