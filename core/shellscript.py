class ShellScript:
    def __init__(self, file_path: str):
        self._script_path = file_path
        self._commands = []

    def add_command(self, commands: str):
        self._commands.append(commands)

    def write(self):
        with open(self._script_path, 'w') as file:
            file.writelines(self._commands)
