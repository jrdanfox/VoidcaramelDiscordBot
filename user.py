class User:

    current_game_start_time = None

    def __init__(self, name):
        self.name = name

    def update_game_start_time(self, gametime):
        self.current_game_start_time = gametime
