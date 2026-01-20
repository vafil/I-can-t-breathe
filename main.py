"""
Проект: I can't breathe
Автор: Ученик 10 класса
Жанр: 2D top-down survival

Описание: Игра про выживание на станции без воздуха. Нужно собирать баллоны и убегать от врагов.
"""

import arcade
import random
import csv
import math
import os

# --- Константы ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
SCREEN_TITLE = "I can't breathe (Alpha)"

# Масштабирование спрайтов
SPRITE_SCALING = 0.5
TILE_SCALING = 0.5

# Скорость игрока
MOVEMENT_SPEED = 3

# Слои (для порядка отрисовки)
LAYER_NAME_WALLS = "Walls"
LAYER_NAME_PLAYER = "Player"
LAYER_NAME_ENEMIES = "Enemies"
LAYER_NAME_ITEMS = "Items"

class MainMenu(arcade.View):
    """ Меню игры """
    def on_show_view(self):
        arcade.set_background_color(arcade.color.DARK_SLATE_BLUE)

    def on_draw(self):
        self.clear()
        arcade.draw_text("I CAN'T BREATHE", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 + 50,
                         arcade.color.WHITE, font_size=40, anchor_x="center")
        arcade.draw_text("Нажми клик чтобы начать выживание", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 20,
                         arcade.color.GRAY, font_size=20, anchor_x="center")

    def on_mouse_press(self, _x, _y, _button, _modifiers):
        # Запускаем игру с 1 уровня
        game_view = GameView()
        game_view.setup(level=1)
        self.window.show_view(game_view)

class GameOverView(arcade.View):
    """ Экран конца игры (смерть или победа) """
    def __init__(self, message="GAME OVER"):
        super().__init__()
        self.message = message

    def on_show_view(self):
        arcade.set_background_color(arcade.color.BLACK)

    def on_draw(self):
        self.clear()
        arcade.draw_text(self.message, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2,
                         arcade.color.RED, font_size=30, anchor_x="center")
        arcade.draw_text("Клик для меню", SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 50,
                         arcade.color.WHITE, font_size=15, anchor_x="center")

    def on_mouse_press(self, _x, _y, _button, _modifiers):
        menu = MainMenu()
        self.window.show_view(menu)

class GameView(arcade.View):
    """ Основной класс игры """

    def __init__(self):
        super().__init__()

        # --- Списки спрайтов ---
        self.scene = None
        self.player_sprite = None
        
        # --- Физика и камеры ---
        self.physics_engine = None
        self.camera = None
        self.gui_camera = None

        # --- Переменные игры ---
        self.level_data = {} # Тут будем хранить данные из CSV
        self.oxygen = 100.0
        self.total_time = 0.0
        self.game_over = False
        
        # Система частиц (какой-нибудь след)
        self.particle_system = None


    def load_level_data(self):
        """ Чтение настроек уровней из CSV """
        # Читаем файл levels.csv
        # Формат: level_id,oxygen_time,enemy_count
        if os.path.exists("levels.csv"):
            with open("levels.csv", mode='r') as infile:
                reader = csv.DictReader(infile)
                for row in reader:
                    self.level_data[int(row['level_id'])] = row
        else:
            print("ОШИБКА: Нет файла levels.csv!")
            # Дефолтные настройки если файла нет
            self.level_data[1] = {'oxygen_time': 60, 'enemy_count': 2}

    def setup(self, level=1):
        """ Настройка уровня """
        self.load_level_data()
        
        current_data = self.level_data.get(level, self.level_data[1])
        
        # Настройка камер
        self.camera = arcade.Camera2D()
        self.gui_camera = arcade.Camera2D()

        # Создаем сцену
        self.scene = arcade.Scene()

        # --- Создание игрока ---
        # Генерируем текстуру программно, чтобы не искать картинки
        player_texture = arcade.make_circle_texture(30, arcade.color.CYAN)
        self.player_sprite = arcade.Sprite(texture=player_texture)
        self.player_sprite.center_x = 100
        self.player_sprite.center_y = 100
        self.scene.add_sprite(LAYER_NAME_PLAYER, self.player_sprite)

        # Система частиц (временно убрана для совместимости с Arcade 3.0)
        self.particle_system = None

        # --- Генерация стен (простой лабиринт) ---
        # Вообще тут лучше бы Tiled использовать, но по ТЗ я делаю кодом или CSV
        self.scene.add_sprite_list(LAYER_NAME_WALLS, use_spatial_hash=True)
        
        # Стены по периметру
        for x in range(0, 1000, 32):
            wall = arcade.SpriteSolidColor(32, 32, arcade.color.GRAY)
            wall.center_x = x
            wall.center_y = 0
            self.scene.add_sprite(LAYER_NAME_WALLS, wall)
            
            wall = arcade.SpriteSolidColor(32, 32, arcade.color.GRAY)
            wall.center_x = x
            wall.center_y = 1000
            self.scene.add_sprite(LAYER_NAME_WALLS, wall)

        for y in range(0, 1000, 32):
            wall = arcade.SpriteSolidColor(32, 32, arcade.color.GRAY)
            wall.center_x = 0
            wall.center_y = y
            self.scene.add_sprite(LAYER_NAME_WALLS, wall)
            
            wall = arcade.SpriteSolidColor(32, 32, arcade.color.GRAY)
            wall.center_x = 1000
            wall.center_y = y
            self.scene.add_sprite(LAYER_NAME_WALLS, wall)

        # Рандомные препятствия
        for _ in range(20):
            wall = arcade.SpriteSolidColor(64, 64, arcade.color.DARK_GRAY)
            wall.center_x = random.randint(100, 900)
            wall.center_y = random.randint(100, 900)
            self.scene.add_sprite(LAYER_NAME_WALLS, wall)

        # --- Враги ---
        enemy_count = int(current_data['enemy_count'])
        for _ in range(enemy_count):
            enemy_texture = arcade.make_circle_texture(30, arcade.color.RED)
            enemy = arcade.Sprite(texture=enemy_texture)
            enemy.center_x = random.randint(200, 800)
            enemy.center_y = random.randint(200, 800)
            
            # Простейший 'AI' - задаем случайную скорость
            enemy.change_x = random.choice([-1, 1])
            enemy.change_y = random.choice([-1, 1])
            
            self.scene.add_sprite(LAYER_NAME_ENEMIES, enemy)

        # --- Предметы (Кислород) ---
        for _ in range(5):
            oxy_texture = arcade.make_circle_texture(15, arcade.color.GREEN)
            item = arcade.Sprite(texture=oxy_texture)
            item.center_x = random.randint(100, 900)
            item.center_y = random.randint(100, 900)
            self.scene.add_sprite(LAYER_NAME_ITEMS, item)

        # --- Физический движок Pymunk ---
        # Гравитация (0,0) так как вид сверху
        self.physics_engine = arcade.PymunkPhysicsEngine(damping=0.7, gravity=(0, 0))
        
        # Добавляем игрока
        self.physics_engine.add_sprite(self.player_sprite,
                                       friction=0.6,
                                       moment_of_inertia=arcade.PymunkPhysicsEngine.MOMENT_INF,
                                       collision_type="player")
        
        # Стены
        self.physics_engine.add_sprite_list(self.scene[LAYER_NAME_WALLS],
                                            friction=0.6,
                                            collision_type="wall",
                                            body_type=arcade.PymunkPhysicsEngine.STATIC)
        
        # Враги
        self.physics_engine.add_sprite_list(self.scene[LAYER_NAME_ENEMIES],
                                            friction=0.6,
                                            moment_of_inertia=arcade.PymunkPhysicsEngine.MOMENT_INF,
                                            collision_type="enemy")

        # Настраиваем кислород
        time_limit = float(current_data['oxygen_time'])
        self.oxygen = time_limit

        arcade.set_background_color(arcade.color.BLACK)

    def on_draw(self):
        """ Рендер всего """
        self.clear()
        
        # Выбираем камеру для игры
        self.camera.use()
        self.scene.draw()
        
        if self.particle_system:
             self.particle_system.draw()

        # Выбираем камеру для интерфейса (HUD)

        # Выбираем камеру для интерфейса (HUD)
        self.gui_camera.use()
        
        # Рисуем кислород
        score_text = f"OXYGEN: {int(self.oxygen)}"
        arcade.draw_text(score_text, 10, 20, arcade.color.WHITE, 14)
        
        if self.oxygen < 10:
             arcade.draw_text("WARNING! LOW OXYGEN!", 300, 500, arcade.color.RED, 20)

    def on_update(self, delta_time):
        """ Обновление логики """
        
        # Двигаем физику
        self.physics_engine.step()

        # Обновляем частицы
        if self.particle_system:
             # self.particle_system.center_xy = self.player_sprite.position
             # self.particle_system.update()
             pass

        # Проверяем не закончился ли кислород
        self.oxygen -= delta_time
        if self.oxygen <= 0:
            view = GameOverView("YOU SUFFOCATED")
            self.window.show_view(view)

        # Движение камеры за игроком
        self.center_camera_to_player()

        # Логика врагов (патруль)
        for enemy in self.scene[LAYER_NAME_ENEMIES]:
            if random.randint(0, 100) < 2: # Иногда меняем направление
                 self.physics_engine.set_velocity(enemy, (random.randint(-100, 100), random.randint(-100, 100)))

            # Если враг врезался в стену, отскакивает (Pymunk сам это делает частично, но добавим логики)
            if enemy.center_x < 0 or enemy.center_x > 1000:
                vx, vy = self.physics_engine.get_velocity(enemy)
                self.physics_engine.set_velocity(enemy, (-vx, vy))

        # Сбор кислорода
        hit_list = arcade.check_for_collision_with_list(self.player_sprite, self.scene[LAYER_NAME_ITEMS])
        for item in hit_list:
            item.remove_from_sprite_lists()
            self.oxygen += 15 # +15 секунд жизни
            
        # Столкновение с врагами
        enemy_hit_list = arcade.check_for_collision_with_list(self.player_sprite, self.scene[LAYER_NAME_ENEMIES])
        if enemy_hit_list:
            view = GameOverView("ATTACKED BY ALIEN")
            self.window.show_view(view)

    def on_key_press(self, key, modifiers):
        """ Управление W A S D """
        if key == arcade.key.W:
            self.physics_engine.set_velocity(self.player_sprite, (0, MOVEMENT_SPEED * 100))
        elif key == arcade.key.S:
            self.physics_engine.set_velocity(self.player_sprite, (0, -MOVEMENT_SPEED * 100))
        elif key == arcade.key.A:
            self.physics_engine.set_velocity(self.player_sprite, (-MOVEMENT_SPEED * 100, 0))
        elif key == arcade.key.D:
            self.physics_engine.set_velocity(self.player_sprite, (MOVEMENT_SPEED * 100, 0))

    def on_key_release(self, key, modifiers):
        """ Останавливаемся если отпустили кнопку (немного инерции будет от Pymunk) """
        if key in [arcade.key.W, arcade.key.S, arcade.key.A, arcade.key.D]:
            # Не останавливаем мгновенно, пусть трение работает
            pass

    def center_camera_to_player(self):
        """ Камера следит за игроком """
        # В Arcade 3.0 Camera2D позиционируется по центру
        self.camera.position = (self.player_sprite.center_x, self.player_sprite.center_y)

def main():
    """ Главная функция запуска """
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    menu_view = MainMenu()
    window.show_view(menu_view)
    arcade.run()

if __name__ == "__main__":
    main()
